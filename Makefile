.PHONY: help install setup build test run clean logs docker-build docker-run docker-shell

# Default target
help:
	@echo "🚀 AIS SITL Platform - Development Commands"
	@echo "=============================================="
	@echo ""
	@echo "Setup & Installation:"
	@echo "  make install          - Install dependencies on macOS"
	@echo "  make setup            - Complete setup (install + build docker)"
	@echo ""
	@echo "Docker Operations:"
	@echo "  make docker-build     - Build Docker image"
	@echo "  make docker-run       - Run PX4 SITL in Docker (Gazebo)"
	@echo "  make docker-shell     - Interactive shell in Docker"
	@echo "  make docker-test      - Run validation tests in Docker"
	@echo ""
	@echo "Local Development:"
	@echo "  make build            - Build PX4 SITL locally (requires native setup)"
	@echo "  make test             - Run tests"
	@echo "  make run              - Run SITL locally"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean            - Clean build artifacts"
	@echo "  make logs             - Show recent logs"
	@echo "  make help             - Show this help message"

# Installation on macOS
install:
	@echo "📦 Running macOS installation script..."
	chmod +x install_macos.sh
	./install_macos.sh

# Complete setup
setup: install docker-build
	@echo "✅ Setup complete!"
	@echo ""
	@echo "Next: Run 'make docker-run' to start SITL simulation"

# Docker: Build image
docker-build:
	@echo "🐳 Building Docker image: ais-sitl:latest"
	docker build -t ais-sitl:latest -f Dockerfile .
	@echo "✅ Docker image built successfully!"

# Docker: Run SITL with Gazebo
docker-run:
	@echo "🚀 Starting PX4 SITL + Gazebo in Docker..."
	@echo "⚠️  This requires X11 forwarding. On macOS, use XQuartz."
	docker run -it --rm \
		-e DISPLAY=host.docker.internal:0 \
		ais-sitl:latest gazebo

# Docker: Interactive shell
docker-shell:
	@echo "🐚 Entering Docker container shell..."
	docker run -it --rm ais-sitl:latest shell

# Docker: Run validation tests
docker-test:
	@echo "🧪 Running validation tests..."
	docker run --rm ais-sitl:latest test
	@echo "✅ Tests completed!"

# Local build (native, requires manual PX4 setup)
build:
	@echo "🔨 Building PX4 SITL locally..."
	@echo "⚠️  This requires native PX4 build environment"
	@echo "Consider using 'make docker-build' instead"

# Run SITL locally
run:
	@echo "⚠️  Ensure Docker is running"
	@make docker-run

# Run tests
test:
	@echo "🧪 Running tests..."
	@make docker-test

# Clean build artifacts
clean:
	@echo "🧹 Cleaning up..."
	rm -rf builds logs
	docker rmi ais-sitl:latest 2>/dev/null || true
	@echo "✅ Cleanup complete"

# Show logs
logs:
	@echo "📋 Recent logs:"
	@ls -lah logs/ 2>/dev/null || echo "No logs directory yet"

# Validate CI locally (requires act)
ci-local:
	@echo "🔍 Validating CI pipeline locally..."
	@command -v act >/dev/null 2>&1 || { echo "Install 'act' first: brew install act"; exit 1; }
	act -j validate-sitl

.SILENT: help
