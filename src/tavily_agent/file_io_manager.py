"""
File I/O utilities for handling payload files and raw data storage.
Manages reading, writing, and versioning of payload JSON files.
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List
from shutil import copy2

# Add src directory to path for absolute imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tavily_agent.config import PAYLOADS_DIR, RAW_DATA_DIR

logger = logging.getLogger(__name__)


class FileIOManager:
    """Manages file operations for payloads and raw data."""
    
    # Test mode: if set, saves will go to temp directory instead
    TEST_OUTPUT_DIR = None
    
    @classmethod
    def set_test_mode(cls, enable: bool = True, output_dir: Optional[str] = None):
        """
        Enable test mode to save outputs to a temporary directory.
        
        Args:
            enable: Whether to enable test mode
            output_dir: Custom output directory (defaults to /tmp/agentic_rag_test)
        """
        if enable:
            if output_dir:
                cls.TEST_OUTPUT_DIR = Path(output_dir)
            else:
                cls.TEST_OUTPUT_DIR = Path("/tmp/agentic_rag_test")
            cls.TEST_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            logger.info(f"✓ Test mode enabled. Outputs will be saved to: {cls.TEST_OUTPUT_DIR}")
        else:
            cls.TEST_OUTPUT_DIR = None
            logger.info("✓ Test mode disabled")
    
    @staticmethod
    def _get_output_dir():
        """Get the appropriate output directory based on test mode."""
        if FileIOManager.TEST_OUTPUT_DIR:
            return FileIOManager.TEST_OUTPUT_DIR
        return PAYLOADS_DIR
    
    @staticmethod
    async def read_payload(company_name: str) -> Optional[Dict[str, Any]]:
        """
        Read payload JSON file for a company.
        
        Args:
            company_name: Company identifier (e.g., 'abridge')
        
        Returns:
            Parsed payload dictionary or None if not found
        """
        payload_path = PAYLOADS_DIR / f"{company_name}.json"
        
        if not payload_path.exists():
            logger.warning(f"Payload file not found: {payload_path}")
            return None
        
        try:
            loop = asyncio.get_event_loop()
            with open(payload_path, "r") as f:
                payload = json.load(f)
            logger.info(f"Loaded payload for {company_name}")
            return payload
        except Exception as e:
            logger.error(f"Error reading payload {payload_path}: {e}")
            return None
    
    @staticmethod
    async def save_payload(
        company_name: str,
        payload: Dict[str, Any],
        version: Optional[str] = None
    ) -> bool:
        """
        Save payload JSON file.
        
        Args:
            company_name: Company identifier
            payload: Payload dictionary to save
            version: Optional version suffix (e.g., 'v1', 'v2')
        
        Returns:
            True if successful, False otherwise
        """
        if version:
            filename = f"{company_name}_{version}.json"
        else:
            filename = f"{company_name}.json"
        
        output_dir = FileIOManager._get_output_dir()
        payload_path = output_dir / filename
        
        try:
            # Try direct write first
            with open(payload_path, "w") as f:
                json.dump(payload, f, indent=2, default=str)
            logger.info(f"✓ Saved payload to {payload_path}")
            return True
        except PermissionError as e:
            # On WSL, try removing file first then recreating
            logger.warning(f"Permission denied on direct write, trying alternate method...")
            try:
                # Remove the file if it exists
                if payload_path.exists():
                    os.remove(payload_path)
                # Now write the new file
                with open(payload_path, "w") as f:
                    json.dump(payload, f, indent=2, default=str)
                logger.info(f"✓ Saved payload after file removal: {payload_path}")
                return True
            except Exception as retry_err:
                logger.error(f"Failed to save payload even after retry: {retry_err}")
                return False
        except Exception as e:
            logger.error(f"Error saving payload {payload_path}: {e}")
            return False
    
    @staticmethod
    async def backup_payload(company_name: str) -> bool:
        """
        Create a versioned backup of the current payload.
        Always backs up from original PAYLOADS_DIR location, saves to test dir if enabled.
        Saves current version as {company_name}_v1.json
        
        Note: On WSL, backup may fail due to Windows mount permission restrictions.
        This is non-critical and the function will continue anyway.
        
        Args:
            company_name: Company identifier
        
        Returns:
            True if backup successful, False otherwise
        """
        try:
            # Always backup from original PAYLOADS_DIR location
            original_path = PAYLOADS_DIR / f"{company_name}.json"
            
            if not original_path.exists():
                logger.warning(f"Cannot backup - file not found: {original_path}")
                return False
            
            # Save backup to test output dir if enabled, otherwise to PAYLOADS_DIR
            output_dir = FileIOManager._get_output_dir()
            
            # Ensure output directory exists
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Find next version number
            version = 1
            while (output_dir / f"{company_name}_v{version}.json").exists():
                version += 1
            
            backup_path = output_dir / f"{company_name}_v{version}.json"
            
            # Read the original file and write to backup
            logger.info(f"Reading original from: {original_path}")
            with open(original_path, 'r') as src:
                content = src.read()
            
            logger.info(f"Writing backup to: {backup_path}")
            with open(backup_path, 'w') as dst:
                dst.write(content)
            
            # Verify backup was created
            if backup_path.exists():
                logger.info(f"✓ Created backup: {backup_path}")
                return True
            else:
                logger.error(f"Backup file was not created: {backup_path}")
                return False
                
        except PermissionError as e:
            # On WSL mounted drives, backup may fail due to Windows permission model
            logger.warning(f"⚠ Backup skipped (permission denied on WSL mount): {e}")
            logger.warning(f"  This is expected on WSL - continuing without backup")
            return True  # Continue - backup is non-critical
        except Exception as e:
            logger.error(f"Error in backup_payload: {e}", exc_info=True)
            return False
    
    @staticmethod
    async def save_raw_data(
        company_name: str,
        tool_name: str,
        data: Dict[str, Any],
        content: str
    ) -> Optional[Path]:
        """
        Save raw tool response data to file.
        
        Args:
            company_name: Company identifier
            tool_name: Tool name (e.g., 'tavily')
            data: Metadata dictionary
            content: Raw content from tool
        
        Returns:
            Path to saved file or None if error
        """
        # Create directory structure
        company_raw_dir = RAW_DATA_DIR / company_name / tool_name
        company_raw_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"{tool_name}_{timestamp}.json"
        file_path = company_raw_dir / filename
        
        try:
            loop = asyncio.get_event_loop()
            
            # Combine metadata with content
            output = {
                "timestamp": timestamp,
                "tool": tool_name,
                "company": company_name,
                "metadata": data,
                "content": content
            }
            
            with open(file_path, "w") as f:
                json.dump(output, f, indent=2, default=str)
            
            logger.info(f"Saved raw data to {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Error saving raw data: {e}")
            return None
    
    @staticmethod
    async def list_company_payloads() -> List[str]:
        """
        List all available company payloads.
        
        Returns:
            List of company names (without .json extension)
        """
        companies = []
        try:
            for file in PAYLOADS_DIR.glob("*.json"):
                # Skip version files
                if "_v" not in file.stem:
                    companies.append(file.stem)
            return sorted(companies)
        except Exception as e:
            logger.error(f"Error listing payloads: {e}")
            return []
    
    @staticmethod
    async def get_raw_data_count(company_name: str, tool_name: str) -> int:
        """
        Count raw data files for a company-tool combination.
        
        Args:
            company_name: Company identifier
            tool_name: Tool name
        
        Returns:
            Number of raw data files
        """
        company_raw_dir = RAW_DATA_DIR / company_name / tool_name
        try:
            return len(list(company_raw_dir.glob("*.json"))) if company_raw_dir.exists() else 0
        except Exception as e:
            logger.error(f"Error counting raw data: {e}")
            return 0


# Global instance
_file_io_manager: Optional[FileIOManager] = None


async def get_file_io_manager() -> FileIOManager:
    """Get or create the global FileIOManager instance."""
    global _file_io_manager
    if _file_io_manager is None:
        _file_io_manager = FileIOManager()
    return _file_io_manager
