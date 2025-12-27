"""Setup and test identity unification feature end-to-end."""
import subprocess
import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def run_command(description, command):
    """Run a command and return success status."""
    logger.info(f"\n{'='*70}")
    logger.info(f"Step: {description}")
    logger.info(f"{'='*70}")
    logger.info(f"Command: {command}")
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            capture_output=True,
            text=True
        )
        
        if result.stdout:
            logger.info(result.stdout)
        
        logger.info(f"✓ {description} completed successfully")
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"✗ {description} failed!")
        if e.stdout:
            logger.error(f"STDOUT:\n{e.stdout}")
        if e.stderr:
            logger.error(f"STDERR:\n{e.stderr}")
        return False


def main():
    """Setup and test everything."""
    logger.info("\n" + "="*70)
    logger.info(" IDENTITY UNIFICATION - SETUP & TEST")
    logger.info("="*70)
    logger.info("\nThis script will:")
    logger.info("  1. Apply database migrations")
    logger.info("  2. Run comprehensive tests")
    logger.info("  3. Verify production readiness")
    logger.info("\nStarting in 3 seconds...")
    
    import time
    time.sleep(3)
    
    steps = [
        ("Apply Database Migrations", "python migrate_db.py"),
        ("Run Identity Unification Tests", "python test_identity_unification.py"),
    ]
    
    all_passed = True
    
    for description, command in steps:
        if not run_command(description, command):
            all_passed = False
            break
    
    logger.info("\n" + "="*70)
    if all_passed:
        logger.info("✓ ALL SETUP AND TESTS COMPLETED SUCCESSFULLY!")
        logger.info("="*70)
        logger.info("\n🎉 Identity unification is ready to push!")
        logger.info("\nNext steps:")
        logger.info("  git add .")
        logger.info("  git commit -m 'Add identity unification feature'")
        logger.info("  git push")
        return 0
    else:
        logger.error("✗ SETUP OR TESTS FAILED")
        logger.error("="*70)
        logger.error("\n❌ Please fix errors before pushing")
        return 1


if __name__ == "__main__":
    sys.exit(main())
