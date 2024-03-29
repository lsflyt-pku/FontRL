import os
import cv2 as cv
import torch
import numpy as np
import argparse
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset

from DRL.ddpg import decode
from DRL.ddpg import move
from DRL.actor import *
from DRL.mover import *
from env import *

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
width = 128

parser = argparse.ArgumentParser()
parser.add_argument('--font', default='298', type=str)
parser.add_argument('--batch_size', default=32, type=int)
args = parser.parse_args()
font = args.font
batch_size = args.batch_size

channels = 3
actionstep = 1
maxstep = 1

parser = argparse.ArgumentParser(description='Learning to Paint')
actor_add = 'model/{}/Paint-run1/actor.pkl'.format(font)
mover_add = 'model/{}/Paint-run1/mover.pkl'.format(font)
output_add='output/{}'.format(font)
print(actor_add)
print(mover_add)
print(output_add)

actor = ResNet(2*channels+3, 18, 50)
actor.load_state_dict(torch.load(actor_add))
actor = actor.to(device).eval()
mover = ResNet_mover(3*channels, 34, 3)
mover.load_state_dict(torch.load(mover_add))
mover = mover.to(device).eval()

if not os.path.exists(output_add):
    os.mkdir(output_add)

T = torch.ones([1, 1, width, width], dtype=torch.float32).to(device)
coord = torch.zeros([1, 2, width, width]).float().to(device)
coord[0, 0, :, :] = torch.linspace(-1, 1, 128)
coord[0, 1, :, :] = torch.linspace(-1, 1, 128)[..., None]


class fontDataset(Dataset):
    def __init__(self, root='2'):
        self.root1 = 'mean'
        self.root2 = root
        self.img_list = os.listdir(os.path.join('data/font_concat', self.root2))
        self.point_src = np.load(os.path.join('data/font_10_stroke', '{}_point.npy'.format(self.root1)))
        self.point_tgt = np.load(os.path.join('data/font_10_stroke', '{}_point.npy'.format(self.root2)))
        self.len = len(self.img_list)
        self.col = []
        cc = [128, 192, 255]
        for i in range(3):
            for j in range(3):
                for k in range(3):
                    self.col.append((cc[i], cc[j], cc[k]))
        self.col.append((64, 192, 255))
        self.col.append((255, 192, 64))
        self.col.append((192, 64, 255))

    def __getitem__(self, index):
        add = self.img_list[index]
        img_id = int(add.split('.')[0].split('_')[0])
        stroke = int(add.split('.')[0].split('_')[1])
        stroke -= 1

        img = cv.imread(os.path.join('data/font_concat', self.root2, add))
        
        img_ref = img[:, 1*width:2*width, :]
        img_point = np.zeros((width, width, 3))
        img_point[0:10, 0:2, 0] = stroke_normal(self.point_src[img_id][stroke])
        img_point[0:10, 0:2, 1] = self.point_tgt[img_id][stroke] / 64 - 1
        img_point[0:10, 0:2, 2] = self.point_src[img_id][stroke] / 64 - 1
        img_src = stroke_draw(stroke_normal(self.point_src[img_id][stroke]))
        img_canvas = stroke_draw(stroke_normal(self.point_src[img_id][stroke]))

        img_src = img_src.transpose((2, 0, 1)) / 255.
        img_canvas = img_canvas.transpose((2, 0, 1)) / 255.
        img_ref = img_ref.transpose((2, 0, 1)) / 255.
        img_point = img_point.transpose((2, 0, 1))

        src = torch.tensor(img_src).to(device).float()
        ref = torch.tensor(img_ref).to(device).float()
        canvas = torch.tensor(img_canvas).to(device).float()
        point = torch.tensor(img_point).to(device).float()
        COL = torch.tensor(self.col[stroke]).float().view(3, 1, 1).to(device)

        return src, ref, canvas, point, COL, img_id, add

    def __len__(self):
        return self.len

cnt = 0
with torch.no_grad():
    dataset = fontDataset(args.font)
    dataloader = DataLoader(dataset=dataset, batch_size=batch_size, shuffle=False, num_workers=0)

    for iter, (src, ref, canvas, point, COL, img_id, add) in enumerate(dataloader):
        for i in range(maxstep):
            step = T.float() * i / maxstep
            state = torch.cat((canvas, ref, step.repeat(src.shape[0], 1, 1, 1), coord.repeat(src.shape[0], 1, 1, 1)), 1)
            action = actor(state.float())
            if i == maxstep-1:
                canvas, _ = decode(point[:, 0, 0:10, 0:2], action, False, point[:, 2, 0:10, 0:2])
                _, point[:, 0, 0:10, 0:2] = decode(point[:, 0, 0:10, 0:2], action, False)
            else:
                canvas, point[:, 0, 0:10, 0:2] = decode(point[:, 0, 0:10, 0:2], action)
            canvas = canvas / 255.
    
        canvas = canvas * COL / 255.
        state = torch.cat((canvas, src, ref), 1)
        action = mover(state.float())
        canvas, point[:, 0, 0:10, 0:2] = move(point[:, 0, 0:10, 0:2], action, W=320)

        canvas = canvas.detach().cpu().numpy()
        canvas = canvas.transpose((0, 2, 3, 1))
        for i in range(canvas.shape[0]):
            if not os.path.exists(os.path.join(output_add, str(int(img_id[i])))):
                os.mkdir(os.path.join(output_add, str(int(img_id[i]))))
            cv.imwrite(os.path.join(output_add, str(int(img_id[i])), add[i]), 255 - canvas[i])

            cnt += 1
            if cnt % 500 == 0:
                print(cnt)
