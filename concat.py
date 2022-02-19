import numpy as np
import cv2 as cv 
import os, sys
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--font', default=0, type=str)
args = parser.parse_args()
font = args.font
cnt = 0
try:
    os.system('mkdir results/{}'.format(font))
except:
    pass
          
root_list = os.listdir(os.path.join('output', font))
print(font, len(root_list))
for root in root_list:
    img_list = os.listdir(os.path.join('output', font, root))
    L = len(img_list)
    IMG = np.ones((320, 320, 3))
    for i in range(L):
        img = cv.imread(os.path.join('output', font, '{}/{}_{}.png'.format(root, root, i+1))) / 255
        IMG *= img
    cv.imwrite('results/{}/{}.png'.format(font, root), IMG * 255)
    cnt += 1
    if cnt % 1000 == 0:
        print(cnt)
