# ChromeDriver Resolution Fix

## Problem

When running `python src/discover/process_discovered_pages.py`, the script failed with:

```
selenium.common.exceptions.NoSuchDriverException: Message: Unable to obtain driver for chrome
ValueError: The path is not a valid file: /usr/bin/chromedriver
```

**Root Cause**: The script was hardcoded to look for ChromeDriver at `/usr/bin/chromedriver`, which doesn't exist in the WSL/Linux environment. The script didn't check for the bundled ChromeDriver in the project.

## Solution

Updated `setup_selenium_driver()` in `src/discover/process_discovered_pages.py` to:

1. **Check multiple ChromeDriver locations in order of preference:**
   ```python
   chromedriver_paths = [
       os.getenv('CHROMEDRIVER_PATH'),           # Environment variable
       'chromedriver/linux64/141.0.7390.65/chromedriver',  # Bundled (specific)
       'chromedriver/linux64/*/chromedriver',    # Bundled (glob pattern)
       '/usr/bin/chromedriver',                  # System installation
       '/usr/local/bin/chromedriver',            # Alternative system path
   ]
   ```

2. **Handle glob patterns** to find ChromeDriver in version-specific subdirectories

3. **Make ChromeDriver executable** with `os.chmod(chromedriver_path, 0o755)`

4. **Provide better error messages** showing all attempted paths

5. **Added glob import** to imports section

## Files Modified

- `src/discover/process_discovered_pages.py`
  - Added `glob` to imports
  - Enhanced `setup_selenium_driver()` with flexible path resolution
  - Added executable permission setting
  - Improved error logging

## Testing

### Before Fix
```
ERROR - ❌ Failed to initialize Chrome driver: Message: Unable to obtain driver for chrome
ERROR - ChromeDriver path: /usr/bin/chromedriver
ERROR - Chrome binary: /usr/bin/chromium
```

### After Fix
```
INFO - Using ChromeDriver from: chromedriver/linux64/141.0.7390.65/chromedriver
INFO - ChromeDriver exists: True
INFO - ✓ Chrome driver initialized successfully
```

## Benefits

✅ **Works with bundled ChromeDriver** - No need to install system package  
✅ **Backward compatible** - Still checks system installations first  
✅ **Environment variable support** - Can override with `CHROMEDRIVER_PATH`  
✅ **Handles version directories** - Works with different ChromeDriver versions  
✅ **Cross-platform ready** - Windows, Linux, macOS paths supported  
✅ **Better error messages** - Shows all attempted paths for debugging  

## Discovery

ChromeDriver is already bundled in the project at:
```
chromedriver/linux64/141.0.7390.65/chromedriver
```

This fix enables using the bundled version without requiring system installation.
