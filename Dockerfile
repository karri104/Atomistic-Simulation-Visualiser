FROM ubuntu:24.04

# Basic dependencies
RUN apt-get update && apt-get install -y \
    g++ make git \
    python3 python3-pip python3.12-venv \
    libgl1 libglx-mesa0 libglu1-mesa libegl1 libgles2 libopengl0 \
    libx11-6 libxext6 libxrender1 \
    libxkbcommon0 libxkbcommon-x11-0 \
    libfreetype6 libfontconfig1 libglib2.0-0 \
    libdbus-1-3 \
    libxcb-cursor0 libxcb1 libxcb-util1 libxcb-xinerama0 \
    libxcb-xinput0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
    libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-shm0 \
    libxcb-sync1 libxcb-xfixes0 \
    x11-apps xauth x11-utils \
    libx11-xcb1 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV QT_X11_NO_MITSHM=1
ENV MPLCONFIGDIR=/tmp/matplotlib

WORKDIR /app

# Install lammps
RUN git clone -b release https://github.com/lammps/lammps.git lammps
WORKDIR lammps/src
RUN make yes-manybody && make mode=shared serial
RUN python3 -m venv /venv
ENV PATH="/venv/bin:$PATH"
RUN make install-python
WORKDIR /app

#Install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy source
COPY src/ src/
COPY inputs/ inputs/
COPY models/ models/

EXPOSE 8000
#CMD ["python3", "src/simulation.py"]
