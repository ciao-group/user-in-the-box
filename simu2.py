# Add simulator_folder to Python path
import sys
sys.path.insert(0, simulator_folder)

# Import the module so that the gym env is registered (replace "mobl_arms_index_pointing" with your simulator's name)
import importlib
importlib.import_module("mobl_arms_index_pointing")

# Initialize the simulator using gymnasium
import gymnasium as gym
simulator = gym.make("uitb:mobl_arms_index_pointing-v0")
