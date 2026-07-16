# PX4 SITL + Gazebo environment for macOS CI/CD (runs on Linux Docker)
# Build: docker build -t ais-sitl:latest .
# Run: docker run -it --rm ais-sitl:latest

FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PX4_HOME=/root/px4
ENV GAZEBO_MODEL_PATH=${PX4_HOME}/Tools/sitl_gazebo/models:$GAZEBO_MODEL_PATH

# Install dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    wget \
    curl \
    python3 \
    python3-pip \
    python3-dev \
    python3-venv \
    pkg-config \
    libopencv-dev \
    libgtk-3-dev \
    libglfw3-dev \
    libgl1-mesa-glx \
    libglu1-mesa \
    libudev-dev \
    libusb-1.0-0-dev \
    genromfs \
    ninja-build \
    jq \
    openjdk-11-jdk \
    && rm -rf /var/lib/apt/lists/*

# Install newer CMake
RUN wget -qO /tmp/cmake.tar.gz https://github.com/Kitware/CMake/releases/download/v3.27.0/cmake-3.27.0-linux-x86_64.tar.gz && \
    tar xzf /tmp/cmake.tar.gz -C /usr/local --strip-components=1 && \
    rm /tmp/cmake.tar.gz

# Install Gazebo Classic (11.x stable)
RUN apt-get update && apt-get install -y \
    gazebo11 \
    libgazebo11-dev \
    ros-humble-gazebo-* \
    && rm -rf /var/lib/apt/lists/*

# Install MAVSDK and pymavlink via pip
RUN pip3 install --no-cache-dir \
    mavsdk==1.4.13 \
    pymavlink==2.4.41 \
    protobuf==4.25.1 \
    pyyaml \
    jinja2 \
    lark

# Clone PX4 Autopilot
RUN git clone --depth 1 https://github.com/PX4/PX4-Autopilot.git ${PX4_HOME}

WORKDIR ${PX4_HOME}

# Build PX4 SITL for gazebo
RUN make distclean && \
    make px4_sitl gazebo

# Create entrypoint for SITL simulation
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["gazebo"]
