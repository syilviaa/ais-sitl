#!/bin/bash
# macOS local development environment setup for AIS SITL Platform
# This script prepares your Mac for PX4 SITL development with Docker

set -e

echo "🚀 AIS SITL Platform - macOS Setup"
echo "=================================="

# Check if Homebrew is installed
if ! command -v brew &> /dev/null; then
    echo "❌ Homebrew not found. Install from: https://brew.sh"
    exit 1
fi

# Install Docker (if not present)
if ! command -v docker &> /dev/null; then
    echo "📦 Installing Docker Desktop..."
    brew install --cask docker
    echo "⚠️  Please start Docker Desktop from Applications folder and re-run this script"
    exit 0
fi

echo "✅ Docker found"

# Install additional macOS tools
echo "📦 Installing development tools..."
brew install git make python3 jq

# Create project structure
echo "📁 Creating project structure..."
mkdir -p docker builds logs

# Build Docker image
echo "🐳 Building Docker image for PX4 SITL + Gazebo..."
docker build -t ais-sitl:latest -f Dockerfile .

if [ $? -eq 0 ]; then
    echo "✅ Docker image built successfully!"
    echo ""
    echo "📝 Next steps:"
    echo "   1. Test SITL: docker run --rm ais-sitl:latest test"
    echo "   2. Run SITL:  docker run -it --rm ais-sitl:latest gazebo"
    echo "   3. Build only: docker run --rm ais-sitl:latest build-only"
else
    echo "❌ Docker build failed"
    exit 1
fi
