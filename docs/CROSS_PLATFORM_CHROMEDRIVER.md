# Cross-Platform ChromeDriver Support

## Overview

The `process_discovered_pages.py` script now supports **Windows, macOS, and Linux** with automatic detection of Chrome/Chromium binaries and ChromeDriver across platforms.

## How It Works

### Two New Helper Functions

#### 1. `get_chrome_binary_path()`
Automatically finds the Chrome/Chromium binary for your platform:

**Windows:**
- `C:\Program Files\Google\Chrome\Application\chrome.exe`
- `C:\Program Files (x86)\Google\Chrome\Application\chrome.exe`
- `C:\Program Files\Chromium\Application\chrome.exe`
- `C:\Program Files (x86)\Chromium\Application\chrome.exe`

**macOS:**
- `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`
- `/Applications/Chromium.app/Contents/MacOS/Chromium`

**Linux:**
- `/usr/bin/chromium`
- `/usr/bin/chromium-browser`
- `/usr/bin/google-chrome`
- `/usr/bin/google-chrome-stable`
- `/snap/bin/chromium`

#### 2. `get_chromedriver_path()`
Automatically finds ChromeDriver in this priority order:

**Windows:**
1. Environment variable: `CHROMEDRIVER_PATH`
2. Project bundled: `chromedriver/win64/141.0.7390.65/chromedriver.exe`
3. Project bundled (glob): `chromedriver/win64/*/chromedriver.exe`
4. Python venv: `{VENV}/Scripts/chromedriver.exe`
5. System: `C:\tools\chromedriver\chromedriver.exe`
6. Current directory: `chromedriver.exe`

**macOS:**
1. Environment variable: `CHROMEDRIVER_PATH`
2. Project bundled: `chromedriver/mac64/141.0.7390.65/chromedriver`
3. Project bundled (glob): `chromedriver/mac64/*/chromedriver`
4. Python venv: `{VENV}/bin/chromedriver`
5. Homebrew: `/usr/local/bin/chromedriver`
6. Apple Silicon: `/opt/homebrew/bin/chromedriver`
7. Current directory: `chromedriver`

**Linux:**
1. Environment variable: `CHROMEDRIVER_PATH`
2. Project bundled: `chromedriver/linux64/141.0.7390.65/chromedriver`
3. Project bundled (glob): `chromedriver/linux64/*/chromedriver`
4. Python venv: `{VENV}/bin/chromedriver`
5. System: `/usr/bin/chromedriver`
6. System alt: `/usr/local/bin/chromedriver`
7. Snap: `/snap/bin/chromium`
8. Current directory: `chromedriver`

## Setup Instructions by Platform

### Windows

**Option 1: Use Project Bundled ChromeDriver** (Recommended if available)
```bash
# Just run - it will find chromedriver/win64/*/chromedriver.exe
python src/discover/process_discovered_pages.py
```

**Option 2: Install via pip**
```bash
pip install chromedriver-binary
python src/discover/process_discovered_pages.py
```

**Option 3: Download Manually**
- Download from: https://chromedriver.chromium.org/
- Place in: `C:\tools\chromedriver\` or project root

**Option 4: Use Environment Variable**
```bash
set CHROMEDRIVER_PATH=C:\path\to\chromedriver.exe
python src/discover/process_discovered_pages.py
```

### macOS

**Option 1: Use Project Bundled ChromeDriver** (Recommended if available)
```bash
# Just run - it will find chromedriver/mac64/*/chromedriver
python src/discover/process_discovered_pages.py
```

**Option 2: Install via Homebrew**
```bash
brew install chromedriver
python src/discover/process_discovered_pages.py
```

**Option 3: Install via pip**
```bash
pip install chromedriver-binary
python src/discover/process_discovered_pages.py
```

### Linux (Docker/WSL)

**Option 1: Use Project Bundled ChromeDriver** (Recommended)
```bash
python src/discover/process_discovered_pages.py
```

**Option 2: Install System Package**
```bash
# Debian/Ubuntu
sudo apt-get install chromium-driver

# Then run
python src/discover/process_discovered_pages.py
```

**Option 3: Use Environment Variable**
```bash
export CHROMEDRIVER_PATH=/usr/bin/chromedriver
python src/discover/process_discovered_pages.py
```

## Environment Variables

Override automatic detection with these environment variables:

```bash
# Specify custom Chrome binary location
export CHROME_BIN=/path/to/chrome

# Specify custom ChromeDriver location
export CHROMEDRIVER_PATH=/path/to/chromedriver

# Then run
python src/discover/process_discovered_pages.py
```

## Troubleshooting

### Issue: "ChromeDriver not found"

**Solution Steps:**

1. **Check what platform was detected:**
   ```bash
   python -c "import sys; print(f'Platform: {sys.platform}')"
   ```

2. **Verify Chrome is installed:**
   ```bash
   # Windows
   where chrome
   
   # macOS
   ls /Applications/Google\ Chrome.app/
   
   # Linux
   which chromium
   ```

3. **Set environment variable explicitly:**
   ```bash
   # Find your chromedriver location first
   which chromedriver           # Linux/macOS
   where chromedriver.exe       # Windows
   
   # Then set it
   export CHROMEDRIVER_PATH=/path/found/above
   # or
   set CHROMEDRIVER_PATH=C:\path\found\above
   ```

4. **Check logs for detailed paths tried:**
   ```bash
   python src/discover/process_discovered_pages.py -v
   # Look for the list of paths checked
   ```

### Issue: Permission Denied (Linux/macOS)

The script automatically makes ChromeDriver executable if needed, but if issues persist:

```bash
chmod +x /path/to/chromedriver
```

### Issue: Chrome Binary Not Found

Chrome might be in a non-standard location. Set it explicitly:

```bash
export CHROME_BIN=/custom/path/to/chrome
python src/discover/process_discovered_pages.py
```

## Testing

To verify your setup works:

```bash
# Run with verbose logging
python src/discover/process_discovered_pages.py -n 1 -v

# Look for output like:
# INFO - Using Chrome binary: /usr/bin/chromium
# INFO - Using ChromeDriver from: chromedriver/linux64/141.0.7390.65/chromedriver
# INFO - ✓ Chrome driver initialized successfully
```

## Supported Platforms

| Platform | Chrome Binary Detection | ChromeDriver Detection | Status |
|----------|------------------------|----------------------|--------|
| Windows | ✅ Yes | ✅ Yes | Fully Supported |
| macOS (Intel) | ✅ Yes | ✅ Yes | Fully Supported |
| macOS (Apple Silicon) | ✅ Yes | ✅ Yes | Fully Supported |
| Linux (Ubuntu/Debian) | ✅ Yes | ✅ Yes | Fully Supported |
| Linux (Docker) | ✅ Yes | ✅ Yes | Fully Supported |
| Linux (WSL) | ✅ Yes | ✅ Yes | Fully Supported |

## Files Modified

- `src/discover/process_discovered_pages.py`
  - Added `get_chrome_binary_path()` function
  - Added `get_chromedriver_path()` function
  - Updated `setup_selenium_driver()` to use helper functions
  - Added platform detection and better error messages

## Key Improvements

✅ **Works on Windows, macOS, and Linux** - Automatic detection  
✅ **Uses project-bundled ChromeDriver** - No system install needed (if available)  
✅ **Handles glob patterns** - Works with version-specific directories  
✅ **Virtual environment aware** - Checks Python venv bin directory  
✅ **Environment variable override** - Full control when needed  
✅ **Better error messages** - Shows all attempted paths  
✅ **Cross-platform compatible** - Single codebase works everywhere  
✅ **Graceful degradation** - Continues if Chrome binary not found (ChromeDriver can still work)  

## Migration from Old Code

If you were using the old Linux-only version:

**Old way (No longer needed):**
```bash
export CHROMEDRIVER_PATH=/usr/bin/chromedriver
python src/discover/process_discovered_pages.py
```

**New way (Automatic):**
```bash
# Just run it - platform detection is automatic
python src/discover/process_discovered_pages.py
```

Both still work, but the new way is more robust and cross-platform!
