# ASV - Atomistic Simulation Visualiser

## General
Once this code has been successfully installed a simulation can be ran by executing the 'simulation.py' python file.

## Installation
There are two installation methods for this project. Manual build and a Dockerised version. **The Dockerised version is easier to run but introduces a potential security risk due to the use of xhost forwarding.**

### Dockerised Install
First you will need to install Docker Engine. Installation for it can be found at their [website](https://docs.docker.com/engine/install/ubuntu/).
Next you'll want to clone this repository by running:
```
git clone https://github.com/karri104/Atomistic-Simulation-Visualiser ASV
```
This will create a directory "ASV", which will be our working directory.
To build and run this code you will then need to forward x11 to Docker.
Simplest way to do this by using xhost.
**If you can do this without the use of xhost, use that different approach since this approach is a potential security risk.**
Anyway, for the xhost approach all you have to do is run `xhost +local:docker` the first time you run this code each session e.g. after restarting your machine.
Then you simply need to run `docker compose up --build` whenever you want to run the code.
The console will include a bunch of errors regarding audio libraries, which can be safely ignored since this project doesn't include sound.

### Manual Install
IMPORTANT: Build instructions currently only tested on an old version of this code on Ubuntu 24.04.

Since some of the components of this project require very specific versions of python to be installed, you will want to build this project in a virtual environment. First you'll want to create a virtual environment to run the code in. For that you need venv and pip for installing packages:

venv & pip:
```
sudo apt update
sudo apt install python3-venv python3-pip
```

Once you have install these you'll want to create a folder to build the code in e.g. "project":
```
mkdir project && cd project/
python3 -m venv ./venv
source venv/bin/activate
```
This "project" file works as our base directory. All commands and files should be ran and placed here unless otherwise specified.

PyQt6:
```
pip3 install pyqt6
```

Lammps:
We will want to build Lammps as a python module:
Detailed installation instruction can be found [here](https://docs.lammps.org/Python_install.html) but we'll go over it now. If your simulation requires any additional packages (like manybody here for tersoff potentials), you will want to add arguments for them in the "make yes-manybody" line e.g. "make yes-manybody yes-kim"
```
git clone -b release https://github.com/lammps/lammps.git lammps
cd lammps/src
make yes-manybody
make mode=shared serial
make install-python
```

Panda3D:
Panda3D needs to be built for a specific version of Python. This is why creating a virtual environment is crucial. Following worked with python 3.12 active in venv.
```
pip3 install panda3d
```

Miscellaneous:
These are miscellaneous other libraries you will need.
```
pip3 install numpy
pip3 install pyqtgraph
pip3 install ase
```

To test if the installation was successful run the "simulation.py" python file in src directory
