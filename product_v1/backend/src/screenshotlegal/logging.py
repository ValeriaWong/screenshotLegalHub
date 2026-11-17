import logging

def configure_logging():
    """Application logs omit raw evidence, prompts, credentials and provider response bodies."""
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(name)s %(message)s')
    logging.getLogger('httpx').setLevel(logging.WARNING)
