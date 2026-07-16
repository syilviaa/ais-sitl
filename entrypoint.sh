#!/bin/bash
set -e

export PX4_HOME=/root/px4
export GAZEBO_MODEL_PATH=${PX4_HOME}/Tools/sitl_gazebo/models:$GAZEBO_MODEL_PATH

cd ${PX4_HOME}

case "${1:-gazebo}" in
    gazebo)
        echo "Starting PX4 SITL with Gazebo..."
        make px4_sitl gazebo
        ;;
    build-only)
        echo "Building PX4 SITL only (no simulation)..."
        make px4_sitl gazebo_build
        ;;
    test)
        echo "Running validation tests..."
        python3 -c "import mavsdk; print(f'MAVSDK version: {mavsdk.__version__}')"
        # Add more validation tests here
        ;;
    shell)
        /bin/bash
        ;;
    *)
        exec "$@"
        ;;
esac
