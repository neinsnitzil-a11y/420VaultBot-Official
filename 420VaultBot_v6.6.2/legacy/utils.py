# simple_vault_bot/utils.py
import subprocess
import asyncio
import os
import logging
import sys
from typing import List, Any, Tuple, Optional

# --- Setup Logging (for utils.py itself) ---
# Ensure logs directory exists before setting up logging
LOGS_DIR = os.path.join(os.path.dirname(__file__), 'data', 'logs')
os.makedirs(LOGS_DIR, exist_ok=True) 

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOGS_DIR, 'vault_whisperer_utils.log')), # Dedicated log for utils
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger("VaultWhisperer_Utils")

def format_bytes(size_bytes: int) -> str:
    """Formats bytes into a human-readable string (e.g., KB, MB, GB)."""
    if size_bytes == 0:
        return "0 B"
    units = ("B", "KB", "MB", "GB", "TB")
    i = 0
    while size_bytes >= 1024 and i < len(units) - 1:
        size_bytes /= 1024
        i += 1
    return f"{size_bytes:.2f} {units[i]}"

def parse_size_string(size_string: str) -> Optional[int]:
    """
    Parses a string like "10MB", "2.5GB", "500KB" into bytes.
    Returns None if parsing fails.
    """
    size_string = size_string.strip().upper()
    if not size_string:
        return None

    try:
        if size_string.endswith("KB"):
            value = float(size_string[:-2]) * 1024
        elif size_string.endswith("MB"):
            value = float(size_string[:-2]) * 1024**2
        elif size_string.endswith("GB"):
            value = float(size_string[:-2]) * 1024**3
        elif size_string.endswith("TB"):
            value = float(size_string[:-2]) * 1024**4
        elif size_string.isdigit(): # Plain bytes
            value = float(size_string)
        else:
            return None # Invalid format
        return int(value)
    except ValueError:
        return None

def paginate_list(data_list: List[Any], page: int, page_size: int) -> Tuple[List[Any], int]:
    """
    Paginates a list and returns the slice for the given page,
    along with the total number of pages.
    """
    if not isinstance(data_list, list):
        log.error(f"paginate_list received non-list data: {type(data_list)}")
        return [], 0
    
    total_items = len(data_list)
    if total_items == 0:
        return [], 0
        
    total_pages = (total_items + page_size - 1) // page_size
    
    # Ensure page is within valid range
    if page < 1:
        page = 1
    elif page > total_pages:
        page = total_pages
        
    start_index = (page - 1) * page_size
    end_index = start_index + page_size
    
    return data_list[start_index:end_index], total_pages

async def run_indexer_script_async():
    """
    Runs the indexer.py script in a separate process asynchronously.
    This allows the bot to remain responsive while indexing occurs.
    """
    project_root = os.path.dirname(os.path.abspath(sys.argv[0]))
    indexer_script_path = os.path.join(project_root, 'indexer.py')

    if not os.path.exists(indexer_script_path):
        log.error(f"Indexer script not found at: {indexer_script_path}")
        raise FileNotFoundError(f"Indexer script not found: {indexer_script_path}")

    command = [sys.executable, indexer_script_path]
    
    log.info(f"Starting indexer script in background: {' '.join(command)}")
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if stdout:
            log.info(f"Indexer (stdout):\n{stdout.decode().strip()}")
        if stderr:
            log.error(f"Indexer (stderr):\n{stderr.decode().strip()}")
        
        if process.returncode != 0:
            log.error(f"Indexer script exited with non-zero code: {process.returncode}")
            raise Exception(f"Indexer script failed with code {process.returncode}")
        log.info("Indexer script completed successfully.")

    except Exception as e:
        log.critical(f"Failed to run indexer script asynchronously: {e}", exc_info=True)
        raise
