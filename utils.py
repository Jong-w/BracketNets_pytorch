"""
This file is filled with miscelaneous classes and functions.
"""
import gym
from gym.wrappers import AtariPreprocessing, TransformReward
from gym_minigrid.wrappers import RGBImgPartialObsWrapper, ImgObsWrapper, FullyObsWrapper, RGBImgObsWrapper, RGBImgObsWrapper
###############################################
import gym
import gym_minigrid
from gym_minigrid.wrappers import *
from gym_minigrid.window import Window
###############################################
import torch
import numpy as np
import cv2
import wandb
from torch.distributions import Categorical


class ReturnWrapper(gym.Wrapper):
    #######################################################################
    # Copyright (C) 2020 Shangtong Zhang(zhangshangtong.cpp@gmail.com)    #
    # Permission given to modify the code as long as you keep this        #
    # declaration at the top                                              #
    #######################################################################
    def __init__(self, env):
        super().__init__(env)
        self.total_rewards = 0
        self.steps = 0

    def step(self, action):
        obs, reward, done, truncated, info = self.env.step(action)
        reward=reward*100-self.steps-1

        # if np.any([done, truncated]):
        #     done = True

        if done or truncated:
            info['returns/episodic_reward'] = self.total_rewards
            info['returns/episodic_length'] = self.steps
            self.total_rewards = 0
            self.steps = 0
        else:
            info['returns/episodic_reward'] = None
            info['returns/episodic_length'] = None

        return obs, reward, done, truncated, info

class ReturnWrapper_wargs(ReturnWrapper):
    #######################################################################
    # Copyright (C) 2020 Shangtong Zhang(zhangshangtong.cpp@gmail.com)    #
    # Permission given to modify the code as long as you keep this        #
    # declaration at the top                                              #
    #######################################################################
    def __init__(self, env, reward_reg=5000, max_steps=1000):
        super().__init__(env)
        self.total_rewards = 0
        self.steps = 0
        self.multiplier = reward_reg
        self.max_steps = max_steps

    def step(self, action):
        obs, reward, done, truncated, info = self.env.step(action)
        # reward = np.ceil(reward)*self.multiplier/(self.steps+1)

        # print reward if reward is not 0
        if reward != 0:
            reward = 1
        reward = reward * self.multiplier - 1
        # reward = reward * self.multiplier - 1
        self.total_rewards += reward
        self.steps += 1

        # if np.any([done, truncated]):
        #     done = True

        #print reward, done, truncated, self.steps in a fancy way
        # print(f"reward: {reward}, done: {done}, truncated: {truncated}, steps: {self.steps}")


        if self.max_steps > self.steps:
            truncated = False
        if done or truncated:
            info['returns/episodic_reward'] = self.total_rewards
            if self.total_rewards != -1000:
                self.total_rewards =0

            info['returns/episodic_length'] = self.steps
            self.total_rewards = 0
            self.steps = 0
        else:
            info['returns/episodic_reward'] = None
            info['returns/episodic_length'] = None

        return obs, reward, done, truncated, info
    def reset(self, *, seed=73060, options=None):
        # super().__init__(env)
        self.total_rewards = 0
        self.steps = 0
        obs, _ = self.env.reset(seed=seed, options=options)
        return obs, _


class FlattenWrapper(gym.core.ObservationWrapper):
    """
    Fully observable gridworld using a compact grid encoding
    """

    def __init__(self, env):
        super().__init__(env)
        imgSpace = env.observation_space.spaces['image']
        self.observation_space = spaces.Box(
            low=0,
            high=255,
            shape=imgSpace.shape,
            dtype='uint8'
        )
    #
    # def step(self, action):
    #     obs, reward, done, info = self.env.step(action)
    #
    #     env = self.unwrapped
    #     tup = (tuple(env.agent_pos), env.agent_dir, action)
    #
    #     # Get the count for this (s,a) pair
    #     pre_count = 0
    #     if tup in self.counts:
    #         pre_count = self.counts[tup]
    #
    #     # Update the count for this (s,a) pair
    #     new_count = pre_count + 1
    #     self.counts[tup] = new_count
    #
    #     bonus = 1 / math.sqrt(new_count)
    #     reward += bonus
    #
    #     return obs, reward, done, info
    def observation(self, obs):
        env = self.unwrapped
        full_grid = env.grid.encode()
        full_grid[env.agent_pos[0]][env.agent_pos[1]] = np.array([
            OBJECT_TO_IDX['agent'],
            COLOR_TO_IDX['red'],
            env.agent_dir
        ])

        return full_grid

def flatten_fullview_wrapperWrapper(env, reward_reg=5000, env_max_step=5000):
    env.max_steps = env_max_step
    env = FullyObsWrapper(env)
    env = FlattenWrapper(env)
    env = ReturnWrapper_wargs(env, reward_reg=reward_reg,  max_steps=env_max_step)
    return env

def flatten_fullview_wrapper(env):
    env = FullyObsWrapper(env)
    env = FlattenWrapper(env)
    env = ReturnWrapper(env)
    return env

def basic_birdview_wrapper(env):
    """Use this as a wrapper only for cartpole etc."""
    # env = RGBImgPartialObsWrapper(env)
    env = RGBImgObsWrapper(env)
    env = ImgObsWrapper(env)
    env = ReturnWrapper(env)
    # env = TransformReward(env, lambda r: np.clip(r, -1, 1))
    return env

def basic_wrapper(env):
    """Use this as a wrapper only for cartpole etc."""
    env = ImgObsWrapper(env)
    env = ReturnWrapper(env)
    env = TransformReward(env, lambda r: np.clip(r, -1, 1))
    return env


def atari_wrapper(env):
    # This is substantially the same CNN as in (Mnih et al., 2016; 2015),
    # the only difference is that in the pre-processing stage
    # we retain all colour channels.
    env = AtariPreprocessing(env, grayscale_obs=False, scale_obs=True)
    env = ReturnWrapper(env)
    env = TransformReward(env, lambda r: np.sign(r))
    return env


def make_envs(env_name, num_envs, partial=1, reward_reg=5000, env_max_step=5000, grid_size=19):
    env_ = gym.make(env_name)

    wrapper_fn = lambda env: flatten_fullview_wrapperWrapper(env, reward_reg=reward_reg, env_max_step=env_max_step)
    # wrapper_fn = flatten_fullview_wrapper

    envs = gym.vector.make(env_name, num_envs, wrappers=wrapper_fn)
    return envs


def take_action(a):
    dist = Categorical(a)
    action = dist.sample()
    logp = dist.log_prob(action)
    entropy = dist.entropy()
    return action.cpu().detach().numpy(), logp, entropy


def init_hidden(n_workers, h_dim, device, grad=False):
    return (torch.zeros(n_workers, h_dim, requires_grad=grad).to(device),
            torch.zeros(n_workers, h_dim, requires_grad=grad).to(device))


def init_obj(n_workers, h_dim, c, device):
    goals = [torch.zeros(n_workers, h_dim, requires_grad=True).to(device)
             for _ in range(c)]
    states = [torch.zeros(n_workers, h_dim).to(device) for _ in range(c)]
    return goals, states


def weight_init(layer):
    if type(layer) == torch.nn.modules.conv.Conv2d or \
            type(layer) == torch.nn.Linear:
        torch.nn.init.orthogonal_(layer.weight.data)
        if layer.bias is not None:
            torch.nn.init.constant_(layer.bias.data, 0)


if __name__=="__main__":
    torch.manual_seed(0)
    env = gym.make('MiniGrid-FourRooms-v0', render_mode='human')
    env.reset()
    for _ in range(100):
        image = env.render()