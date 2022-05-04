import numpy as np
import mujoco_py
from gym import spaces
import xml.etree.ElementTree as ET
import os

from .reward_functions import NegativeExpDistanceWithHitBonus

from UIB.utils.functions import project_path, parent_path
from UIB.tasks.base import BaseTask

class Pointing(BaseTask):

  xml_file = os.path.join(parent_path(__file__), "task.xml")

  def __init__(self, sim, end_effector, shoulder, **kwargs):
    super().__init__(sim)

    # This task requires an end-effector to be defined TODO could be either body or geom, or why not a site
    self.end_effector = end_effector

    # Also a shoulder that is used to define the location of target plane
    self.shoulder = shoulder

    # Get an rng
    self.rng = kwargs.get("rng", np.random.default_rng(None))

    # Get action sample freq
    action_sample_freq = kwargs["action_sample_freq"]

    # Use early termination if target is not hit in time
    self.steps_since_last_hit = 0
    self.max_steps_without_hit = action_sample_freq*4
    self.steps = 0

    # Define a maximum number of trials (if needed for e.g. evaluation / visualisation)
    self.trial_idx = 0
    self.max_trials = kwargs.get('max_trials', 10)
    self.targets_hit = 0

    # Dwelling based selection -- fingertip needs to be inside target for some time
    self.steps_inside_target = 0
    self.dwell_threshold = int(0.5*action_sample_freq)

    # Radius limits for target
    self.target_radius_limit = kwargs.get('target_radius_limit', np.array([0.05, 0.15]))
    self.target_radius = self.target_radius_limit[0]

    # Minimum distance to new spawned targets is twice the max target radius limit
    self.new_target_distance_threshold = 2*self.target_radius_limit[1]

    # Define a default reward function
    #if self.reward_function is None:
    self.reward_function = NegativeExpDistanceWithHitBonus(k=10)

    # Do a forward step so stuff like geom and body positions are calculated
    sim.forward()

    # Define plane where targets will be spawned: 0.5m in front of shoulder, or the "humphant" body. Note that this
    # body is not fixed but moves with the shoulder, so the model is assumed to be in initial position
    self.target_origin = sim.data.get_body_xpos(self.shoulder) + np.array([0.5, 0, 0])
    self.target_position = self.target_origin.copy()
    self.target_limits_y = np.array([-0.3, 0.3])
    self.target_limits_z = np.array([-0.3, 0.3])

    # Update plane location
    self.target_plane_geom_idx = sim.model.geom_name2id("target-plane")
    self.target_plane_body_idx = sim.model.body_name2id("target-plane")
    sim.model.geom_size[self.target_plane_geom_idx] = np.array([0.005,
                                                                (self.target_limits_y[1] - self.target_limits_y[0])/2,
                                                                (self.target_limits_z[1] - self.target_limits_z[0])/2])
    sim.model.body_pos[self.target_plane_body_idx] = self.target_origin

    # Set camera angle TODO need to rethink how cameras are implemented
    sim.model.cam_pos[sim.model.camera_name2id('for_testing')] = np.array([1.1, -0.9, 0.95])
    sim.model.cam_quat[sim.model.camera_name2id('for_testing')] = np.array(
      [0.6582, 0.6577, 0.2590, 0.2588])
    #sim.model.cam_pos[sim.model.camera_name2id('for_testing')] = np.array([-0.8, -0.6, 1.5])
    #sim.model.cam_quat[sim.model.camera_name2id('for_testing')] = np.array(
    #  [0.718027, 0.4371043, -0.31987, -0.4371043])

  def update(self, sim):

    finished = False
    info = {"termination": False, "target_spawned": False}

    # Get end-effector position
    ee_position = sim.data.get_geom_xpos(self.end_effector)

    # Distance to target
    dist = np.linalg.norm(self.target_position - (ee_position - self.target_origin))

    # Check if fingertip is inside target
    if dist < self.target_radius:
      self.steps_inside_target += 1
      info["inside_target"] = True
    else:
      self.steps_inside_target = 0
      info["inside_target"] = False

    if info["inside_target"] and self.steps_inside_target >= self.dwell_threshold:

      # Update counters
      info["target_hit"] = True
      self.trial_idx += 1
      self.targets_hit += 1
      self.steps_since_last_hit = 0
      self.steps_inside_target = 0
      self.spawn_target(sim)
      info["target_spawned"] = True

    else:

      info["target_hit"] = False

      # Check if time limit has been reached
      self.steps_since_last_hit += 1
      if self.steps_since_last_hit >= self.max_steps_without_hit:
        # Spawn a new target
        self.steps_since_last_hit = 0
        self.trial_idx += 1
        self.spawn_target(sim)
        info["target_spawned"] = True

    # Check if max number trials reached
    if self.trial_idx >= self.max_trials:
      finished = True
      info["termination"] = "max_trials_reached"

    # Increase counter
    self.steps += 1

    # Calculate reward; note, inputting distance to surface into reward function, hence distance can be negative if
    # fingertip is inside target
    reward = self.reward_function.get(self, dist-self.target_radius, info)

    # Add an effort cost to reward
    #reward -= self.effort_term.get(self)

    return reward, finished, info

  def get_state(self):
    state = super().get_state()
    state["target_position"] = self.target_origin.copy()+self.target_position.copy()
    state["target_radius"] = self.target_radius
    state["target_hit"] = False
    state["inside_target"] = False
    state["target_spawned"] = False
    state["trial_idx"] = self.trial_idx
    state["targets_hit"] = self.targets_hit
    return state

  def reset(self, sim, rng):

    # Reset counters
    self.steps_since_last_hit = 0
    self.steps = 0
    self.steps_inside_target = 0
    self.trial_idx = 0
    self.targets_hit = 0

    # Spawn a new location
    self.spawn_target(sim)

  def spawn_target(self, sim):

    # Sample a location; try 10 times then give up (if e.g. self.new_target_distance_threshold is too big)
    for _ in range(10):
      target_y = self.rng.uniform(*self.target_limits_y)
      target_z = self.rng.uniform(*self.target_limits_z)
      new_position = np.array([0, target_y, target_z])
      distance = np.linalg.norm(self.target_position - new_position)
      if distance > self.new_target_distance_threshold:
        break
    self.target_position = new_position

    # Set location
    sim.model.body_pos[sim.model._body_name2id["target"]] = self.target_origin + self.target_position

    # Sample target radius
    self.target_radius = self.rng.uniform(*self.target_radius_limit)

    # Set target radius
    sim.model.geom_size[sim.model._geom_name2id["target"]][0] = self.target_radius

    sim.forward()