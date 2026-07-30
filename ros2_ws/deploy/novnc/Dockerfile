FROM ros:jazzy-ros-base

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    ros-jazzy-ros-gz-sim \
    ros-jazzy-nav2-minimal-tb3-sim \
    ros-jazzy-turtlebot3-description \
    ros-jazzy-xacro \
    dbus-x11 \
    fluxbox \
    mesa-utils \
    novnc \
    websockify \
    x11vnc \
    xvfb \
    xterm \
    && rm -rf /var/lib/apt/lists/*

COPY start_gazebo_novnc.sh /usr/local/bin/start_gazebo_novnc.sh
RUN chmod +x /usr/local/bin/start_gazebo_novnc.sh

EXPOSE 6080

CMD ["/usr/local/bin/start_gazebo_novnc.sh"]
