import os
import argparse
from shared.config import settings
from shared.logging import get_logger

logger = get_logger("translator")

def main():
    parser = argparse.ArgumentParser(description="Secubrief Translator Batch Job")
    parser.add_argument("--batch", action="store_true", help="Run batch translation")
    args = parser.parse_args()
    
    logger.info("Translator starting", {"config": settings.safe_dump()})
    
    # Check GPU visibility (CUDA_VISIBLE_DEVICES or through torch)
    if "CUDA_VISIBLE_DEVICES" in os.environ:
        logger.info(f"CUDA_VISIBLE_DEVICES: {os.environ['CUDA_VISIBLE_DEVICES']}")
    else:
        logger.info("CUDA_VISIBLE_DEVICES not set (using all visible GPUs or none)")
        
    try:
        import torch
        num_gpus = torch.cuda.device_count()
        logger.info(f"PyTorch sees {num_gpus} GPUs")
        for i in range(num_gpus):
            logger.info(f"GPU {i}: {torch.cuda.get_device_name(i)}")
    except ImportError:
        logger.warning("PyTorch not installed or cannot import torch")

    if args.batch:
        logger.info("Running batch translation...")
        # Model loading intentionally omitted
        logger.info("Batch translation completed.")
    else:
        logger.info("Translator idle. Use --batch to run.")

if __name__ == "__main__":
    main()
