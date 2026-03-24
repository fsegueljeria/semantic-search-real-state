"""
ETL Pipeline Main Entry Point
============================

Command-line interface for running the ETL pipeline.
"""

import argparse
import sys
import time
from pathlib import Path
from loguru import logger

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from config.settings import settings
from src.etl.loader import ETLLoader
from src.db.client import qdrant
from src.services.embedder import embedder


def setup_logging() -> None:
    """Configure logging for the ETL pipeline."""
    # Remove default handler
    logger.remove()
    
    # Add console handler
    logger.add(
        sys.stderr,
        level=settings.log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True,
    )
    
    # Add file handler for detailed logs
    log_file = Path("etl_pipeline.log")
    logger.add(
        log_file,
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation="10 MB",
        retention="7 days",
    )
    
    logger.info(f"Logging configured. Log file: {log_file}")


def verify_dependencies() -> bool:
    """Verify that all dependencies are available."""
    logger.info("Verifying dependencies...")
    
    try:
        # Test CSV file
        csv_path = Path(settings.csv_file_path)
        if not csv_path.exists():
            logger.error(f"CSV file not found: {csv_path}")
            return False
        
        file_size_mb = csv_path.stat().st_size / (1024 * 1024)
        logger.info(f"CSV file found: {csv_path} ({file_size_mb:.1f} MB)")
        
        # Test Qdrant connection
        try:
            client_info = qdrant.client.get_collections()
            logger.success(f"Qdrant connection successful. Collections: {len(client_info.collections)}")
        except Exception as e:
            logger.error(f"Cannot connect to Qdrant: {e}")
            logger.error("Make sure Qdrant is running: docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant")
            return False
        
        # Test embedding service
        try:
            model_info = embedder.get_model_info()
            logger.info(f"Embedding model: {model_info['model_name']} (dim: {model_info['dimension']})")
            
            # Quick embedding test
            test_embedding = embedder.embed_text("test casa en santiago")
            logger.success(f"Embedding service working. Test vector length: {len(test_embedding)}")
            
        except Exception as e:
            logger.error(f"Embedding service error: {e}")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"Dependency verification failed: {e}")
        return False


def run_etl_pipeline(
    recreate_collection: bool = False,
    skip_rows: int = 0,
    use_versioned_collection: bool = False,
    switch_alias: bool = False,
) -> None:
    """Run the complete ETL pipeline."""
    start_time = time.time()
    
    try:
        target_collection = settings.qdrant_collection_name
        if use_versioned_collection:
            target_collection = qdrant.build_versioned_collection_name(
                settings.qdrant_collection_name,
                settings.qdrant_collection_version_suffix,
            )
            logger.info(f"Using versioned target collection: {target_collection}")

        if recreate_collection:
            logger.warning(f"Recreate requested: deleting collection '{target_collection}'")
            if not qdrant.delete_collection(target_collection):
                raise RuntimeError("Failed to delete collection")
        
        # Initialize pipeline
        loader = ETLLoader(skip_rows=skip_rows, target_collection=target_collection)
        
        # Run pipeline
        final_stats = loader.run_pipeline()
        
        # Calculate total time
        total_time = time.time() - start_time
        
        # Final report
        logger.info("="*60)
        logger.info("🎉 ETL PIPELINE COMPLETED SUCCESSFULLY")
        logger.info("="*60)
        logger.info(f"⏱️  Total Execution Time: {total_time:.1f} seconds ({total_time/60:.1f} minutes)")
        logger.info(f"📊 Records per Second: {final_stats['Total Records Processed']/total_time:.1f}")
        logger.info("="*60)
        
        # Verify collection
        collection_info = qdrant.get_collection_info(target_collection)
        if collection_info:
            points_count = collection_info.points_count
            logger.info(f"✅ Collection '{target_collection}' now contains {points_count} vectors")

        if switch_alias:
            logger.info(
                f"Switching alias '{settings.qdrant_collection_alias}' -> '{target_collection}'"
            )
            if not qdrant.switch_alias_atomically(settings.qdrant_collection_alias, target_collection):
                raise RuntimeError("Failed to switch collection alias")
        
    except Exception as e:
        logger.error(f"💥 Pipeline failed: {e}")
        sys.exit(1)


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Semantic Search ETL Pipeline")
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Delete the Qdrant collection and reload from CSV (cleans corrupted data). No confirmation prompt.",
    )
    parser.add_argument(
        "-y", "--yes",
        action="store_true",
        help="Skip confirmation prompt (use with scripts).",
    )
    parser.add_argument(
        "--skip-rows",
        type=int,
        default=0,
        help="Skip first N parsed rows from CSV (resume interrupted loads without duplicating).",
    )
    parser.add_argument(
        "--use-versioned-collection",
        action="store_true",
        help="Load into <collection>_<version_suffix> instead of base collection.",
    )
    parser.add_argument(
        "--switch-alias",
        action="store_true",
        help="Switch active alias to target collection after successful ETL run.",
    )
    args = parser.parse_args()
    
    setup_logging()
    
    logger.info("🚀 Starting Semantic Search ETL Pipeline")
    logger.info(f"📁 CSV File: {settings.csv_file_path}")
    logger.info(f"🧠 Model: {settings.embedding_model}")
    logger.info(f"📦 Batch Size: {settings.batch_size}")
    logger.info(f"🗄️ Collection: {settings.qdrant_collection_name}")
    if args.recreate:
        logger.info("🔄 Mode: --recreate (will delete collection and reload)")
    if args.skip_rows > 0:
        logger.info(f"⏭️  Mode: --skip-rows {args.skip_rows} (resume load)")
    if args.use_versioned_collection:
        logger.info(f"🧩 Mode: versioned collection suffix '{settings.qdrant_collection_version_suffix}'")
    if args.switch_alias:
        logger.info(f"🔀 Mode: will switch alias '{settings.qdrant_collection_alias}' on success")
    
    # Verify environment
    if not verify_dependencies():
        logger.error("❌ Dependency verification failed")
        sys.exit(1)
    
    # Confirm execution unless --recreate or -y
    if not args.recreate and not args.yes:
        logger.warning("⚠️  This will process the entire CSV file and upload to Qdrant")
        response = input("Continue? (y/N): ").strip().lower()
        if response != 'y':
            logger.info("Pipeline cancelled by user")
            sys.exit(0)
    
    # Run pipeline
    run_etl_pipeline(
        recreate_collection=args.recreate,
        skip_rows=args.skip_rows,
        use_versioned_collection=args.use_versioned_collection,
        switch_alias=args.switch_alias,
    )


if __name__ == "__main__":
    main()