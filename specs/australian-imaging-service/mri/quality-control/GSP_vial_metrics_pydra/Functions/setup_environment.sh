#!/bin/bash
# Setup script for GSP_vial_metrics_pydra
# This script sets up the Python environment and installs all dependencies

set -e  # Exit on error

echo "=========================================="
echo "GSP Vial Metrics - Environment Setup"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if pyenv is installed
if ! command -v pyenv &> /dev/null; then
    echo -e "${RED}✗ pyenv not found!${NC}"
    echo "Please install pyenv first:"
    echo "  brew install pyenv"
    exit 1
fi

echo -e "${GREEN}✓ pyenv found${NC}"

# Python version to use
PYTHON_VERSION="3.13.7"
VENV_NAME="gsp_vial_metrics"

# Check if Python version is installed
if ! pyenv versions | grep -q "$PYTHON_VERSION"; then
    echo -e "${YELLOW}Installing Python $PYTHON_VERSION...${NC}"
    pyenv install $PYTHON_VERSION
else
    echo -e "${GREEN}✓ Python $PYTHON_VERSION already installed${NC}"
fi

# Set local Python version
echo -e "${YELLOW}Setting local Python version to $PYTHON_VERSION...${NC}"
pyenv local $PYTHON_VERSION

# Check if virtual environment exists
if pyenv virtualenvs | grep -q "$VENV_NAME"; then
    echo -e "${YELLOW}Virtual environment '$VENV_NAME' already exists${NC}"
    read -p "Do you want to recreate it? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Deleting existing environment...${NC}"
        pyenv virtualenv-delete -f $VENV_NAME
    else
        echo -e "${GREEN}Using existing environment${NC}"
        pyenv local $VENV_NAME
        echo -e "${GREEN}✓ Environment activated${NC}"
        exit 0
    fi
fi

# Create virtual environment
echo -e "${YELLOW}Creating virtual environment '$VENV_NAME'...${NC}"
pyenv virtualenv $PYTHON_VERSION $VENV_NAME

# Activate the virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
pyenv local $VENV_NAME

# Upgrade pip
echo -e "${YELLOW}Upgrading pip...${NC}"
pip install --upgrade pip

# Install dependencies
echo ""
echo "=========================================="
echo "Installing Python Dependencies"
echo "=========================================="
echo ""

# Core dependencies
echo -e "${YELLOW}Installing core packages...${NC}"
pip install numpy
pip install pandas
pip install matplotlib
pip install scipy
pip install pydra

echo ""
echo -e "${GREEN}✓ All Python packages installed${NC}"

# Check for required external tools
echo ""
echo "=========================================="
echo "Checking External Dependencies"
echo "=========================================="
echo ""

# Function to check if command exists
check_command() {
    if command -v $1 &> /dev/null; then
        echo -e "${GREEN}✓ $1 found${NC}"
        return 0
    else
        echo -e "${RED}✗ $1 not found${NC}"
        return 1
    fi
}

MISSING_TOOLS=0

# Check ANTs
if ! check_command antsRegistrationSyN.sh; then
    echo "  Install ANTs: https://github.com/ANTsX/ANTs"
    MISSING_TOOLS=1
fi

# Check MRtrix3
if ! check_command mrinfo; then
    echo "  Install MRtrix3: https://www.mrtrix.org/"
    MISSING_TOOLS=1
fi

# List of MRtrix3 commands we need
MRTRIX_COMMANDS="mrconvert mrgrid mrstats mrtransform mrcat mrmath mrview"
for cmd in $MRTRIX_COMMANDS; do
    check_command $cmd > /dev/null || MISSING_TOOLS=1
done

if [ $MISSING_TOOLS -eq 1 ]; then
    echo ""
    echo -e "${YELLOW}⚠ Warning: Some external tools are missing${NC}"
    echo "The Python environment is ready, but you need to install:"
    echo "  - ANTs (for registration)"
    echo "  - MRtrix3 (for image processing)"
    echo ""
else
    echo ""
    echo -e "${GREEN}✓ All external tools found${NC}"
fi

# Create .python-version file for automatic activation
echo "$VENV_NAME" > .python-version

# Summary
echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Virtual environment: $VENV_NAME"
echo "Python version: $PYTHON_VERSION"
echo ""
echo "The environment will activate automatically when you cd into this directory."
echo ""
echo "To manually activate:"
echo "  pyenv activate $VENV_NAME"
echo ""
echo "To deactivate:"
echo "  pyenv deactivate"
echo ""
echo "Installed Python packages:"
pip list | grep -E "(numpy|pandas|matplotlib|scipy|pydra)"
echo ""

# Test Python
echo "Testing Python installation..."
python --version
echo ""

echo -e "${GREEN}✓ Ready to run!${NC}"
echo ""
echo "Example command:"
echo "  python pydra_phantom_iterative.py single \\"
echo "    /path/to/image.nii.gz \\"
echo "    --template-dir /path/to/TemplateData \\"
echo "    --output-dir /path/to/Outputs \\"
echo "    --rotation-lib /path/to/TemplateData/rotations.txt"
echo ""


# add ANTs to path
export PATH=/Applications/ants-2.6.3/bin:$PATH