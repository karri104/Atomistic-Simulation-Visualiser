# ASV - Atomistic Simulation Visualiser

## General
Once this code has been successfully installed a simulation can be ran by executing the 'simulation.py' python file.

## Installation
IMPORTANT: These instruction assume administrator rights. Non-privileged build instructions currently WIP. Build instructions currently only tested on Ubuntu 24.04.

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
