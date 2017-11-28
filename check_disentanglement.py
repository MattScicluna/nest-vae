import os
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from torch.autograd import Variable

import torchvision
from torchvision import datasets, transforms

from tensorboardX import SummaryWriter

from main import VAE


# Getting the most recent checkpoint
if os.path.exists('./.saves/beta-vae/'):
    print('Great. Directory exists')
else:
    raise('Please correct the Directory info in the file check_disentanglement.py')

ckpts = [file for file in os.listdir('./.saves/beta-vae/') if file[-5:]=='.ckpt']
ckpt_name = './.saves/beta-vae/beta-vae_%d.ckpt' % (len(ckpts),)
ckpt = torch.load(state, ckpt_name)
print('Checkpoint loaded: {}'.format(ckpt_name))


# Loading the checkpoint into our model
vae = VAE()
vae.load_state_dict(ckpt['model'])

# Writing the images for disentanglement
writer = SummaryWriter('./.logs/beta-vae')

z_dim = vae.z_dim
n_images = 10

for i in range(z_dim):
    z = np.random.uniform(-5,5,(z_dim))
    z = np.asarray([list(z)]*n_images)
    z.T[i] = np.linspace(-5,5,n_images)
    reconst_logits, _, _ = vae(fixed_x)
    reconst_grid = torchvision.utils.make_grid(F.sigmoid(reconst_logits).data,
        normalize=True, scale_each=True)
    writer.add_image('beta-vae/feature_{}'.format(i), reconst_grid, epoch)
    

