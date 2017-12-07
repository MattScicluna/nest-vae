import os
import argparse

# QKFIX: Add the parent path to PYTHONPATH
import sys
sys.path.insert(0, 'tristan')

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.autograd import Variable

import torchvision
from torchvision import transforms
from tensorboardX import SummaryWriter

from transforms import RandomMask
from datasets import DSprites, Reconstruction

from models.vae_dsprites import VAE
from utils.torch_utils import to_var
from utils.io_utils import get_latest_checkpoint


parser = argparse.ArgumentParser(description='VAE')
parser.add_argument('--batch-size', type=int, default=100, metavar='N',
                    help='Input batch size for training (default: 100)')
parser.add_argument('--num-steps', type=int, default=200000, metavar='N',
                    help='Number training steps (default: 500000)')
parser.add_argument('--log-interval', type=int, default=200, metavar='N',
                    help='Log interval, number of steps before save/image '
                    'in Tensorboard (default: 200)')
parser.add_argument('--beta', type=float, default=1, metavar='N',
                    help='Value of the hyperparameter beta (default: 1)')
parser.add_argument('--obs', type=str, default='normal',
                    help='Type of the observation model (in [normal, '
                    'bernoulli], default: normal)')
parser.add_argument('--pretrained', type=str, default=None,
                    help='Path to pretrained model')

parser.add_argument('--no-cuda', action='store_true', default=False,
                    help='Disables CUDA training')
parser.add_argument('--seed', type=int, default=7691, metavar='S',
                    help='Random seed (default: 7691)')
parser.add_argument('--output-folder', type=str, default='vae',
                    help='Name of the output folder (default: vae)')
args = parser.parse_args()
args.cuda = not args.no_cuda and torch.cuda.is_available()

torch.manual_seed(args.seed)
if args.cuda:
    torch.cuda.manual_seed(args.seed)

if 'SLURM_JOB_ID' in os.environ:
    args.output_folder += '-{0}'.format(os.environ['SLURM_JOB_ID'])
if not os.path.exists('./.saves/{0}'.format(args.output_folder)):
    os.makedirs('./.saves/{0}'.format(args.output_folder))

# Data loading
dataset = DSprites(root='./data/dsprites',
    transform=transforms.ToTensor(), download=True)

data_loader = torch.utils.data.DataLoader(dataset=dataset,
    batch_size=args.batch_size, shuffle=True)

# Model
model = VAE()
if args.cuda:
    model.cuda()
if args.pretrained is not None:
    with open(get_latest_checkpoint(args.pretrained), 'r') as f:
        state_dict = torch.load(f)
        state_dict = state_dict['model']
    model.load(state_dict)
writer = SummaryWriter('./.logs/{0}'.format(args.output_folder))

# Optimizer
optimizer = torch.optim.Adam(model.parameters(), lr=5e-4)

# Fixed input for Tensorboard
fixed_x, _ = next(iter(data_loader))
fixed_grid = torchvision.utils.make_grid(fixed_x, normalize=True, scale_each=True)
writer.add_image('original', fixed_grid, 0)
fixed_x = to_var(fixed_x, args.cuda)

steps = 0
while steps < args.num_steps:
    for images, _ in data_loader:
        images = to_var(images, args.cuda)
        logits, mu, log_var = model(images)

        if args.obs == 'normal':
            # QKFIX: We assume here that the image is in B&W
            reconst_loss = F.mse_loss(F.sigmoid(logits), images, size_average=False)
        elif args.obs == 'bernoulli':
            reconst_loss = F.binary_cross_entropy_with_logits(logits, images, size_average=False)
        else:
            raise ValueError('Argument `obs` must be in [normal, bernoulli]')

        beta = args.beta * float(steps - 10000) / 10000.
        beta = min(args.beta, max(0., beta))
        kl_divergence = 0.5 * beta * torch.sum(mu ** 2 + torch.exp(log_var) - log_var - 1)
        loss = reconst_loss + kl_divergence

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        writer.add_scalar('loss', loss.data[0], steps)
        writer.add_scalar('reconst_loss', reconst_loss.data[0], steps)
        writer.add_scalar('kl_divergence', kl_divergence.data[0], steps)
        writer.add_scalar('beta', beta, steps)

        writer.add_histogram('mu', mu.data, steps)
        writer.add_histogram('log_var', log_var.data, steps)

        if (steps > 0) and (steps % args.log_interval == 0):
            # Save the reconstructed images
            logits, _, _ = model(fixed_x)
            grid = torchvision.utils.make_grid(F.sigmoid(logits).data,
                normalize=True, scale_each=True)
            writer.add_image('reconstruction', grid, steps)

            # Save the checkpoint
            state = {
                'steps': steps,
                'model': model.state_dict(),
                'optimizer': optimizer.state_dict(),
                'loss': loss.data[0],
                'args': args
            }
            torch.save(state, './.saves/{0}/{0}_{1:d}.ckpt'.format(
                args.output_folder, steps))

        steps += 1
        if steps >= args.num_steps:
            break
