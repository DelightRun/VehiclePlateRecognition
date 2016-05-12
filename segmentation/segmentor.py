#!/usr/bin/python
import sys
import os

import cv2
import numpy as np
from matplotlib import pyplot as plt

models_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'erfilter_train', 'trained_classifiers')

def get_chars(image, minProb1=0.5, minProb2=0.75):
    height, width = image.shape[:2]
    print("Image size: %d x %d" % (width, height))

    # Extract channels to be processed individually
    channels = cv2.text.computeNMChannels(image)
    channels[3] = cv2.equalizeHist(channels[3])    # equalize Light channel
    # Append negative channels to detect ER- (bright regions over dark background)
    for channel in channels[:-1]:
        channels.append(255-channel)

    erc1 = cv2.text.loadClassifierNM1(os.path.join(models_dir, 'trained_classifierNM1.xml'))
    er1 = cv2.text.createERFilterNM1(erc1, 1, 0.0015, 1.0, 0.5, True, 0.1)

    erc2 = cv2.text.loadClassifierNM2(os.path.join(models_dir, 'trained_classifierNM2.xml'))
    er2 = cv2.text.createERFilterNM2(erc2, 0.75)

    rects = []
    # Apply the default cascade classifier to each independent channel (could be done in parallel in C++)
    for channel in channels:
        for region in cv2.text.detectRegions(channel, er1, er2):
            rect = cv2.boundingRect(region.reshape(-1,1,2))

            # filte by height ratio and width-height ratio and x position
            if rect[0] > 0.05*width and rect[3] >= 0.4*height and rect[2]*0.3 <= rect[3] < rect[2]*10:
                rects.append(rect)

    height_mean = np.mean([rect[3] for rect in rects]).tolist()
    rects = [rect for rect in rects if abs(rect[3]-height_mean)/height < 0.15]

    # sort by x coordinate
    rects.sort(key=lambda r : r[0])

    def center(rect):
        return (round(rect[0] + rect[2]/2), round(rect[1] + rect[3]/2))

    def center_delta(rectA, rectB):
        return (center(rectA)[0]-center(rectB)[0], center(rectA)[1]-center(rectB)[1])

    bins = [[rects[0]]]
    for i in range(1, len(rects)):
        # TODO: judge by overlap
        if abs(center_delta(rects[i], rects[i-1])[0]) > 0.4*rects[i-1][2]:
            bins.append([rects[i]])
        else:
            bins[-1].append(rects[i])

    # sort by number of rects in each bin
    bins.sort(key=lambda b : len(b), reverse=True)
    # get most posible bins, at most 6 bins
    bins = bins[:min(len(bins),6)]

    def rects_max(rects):
        rects.sort(key=lambda rect : rect[2]*rect[3])
        return rects[-1]

    # get avarage size and position of each bin
    rects = [rects_max(bin) for bin in bins]

    # sort by x coordinate
    rects.sort(key=lambda r : r[0])

    char_centers = [center(rect) for rect in rects]
    char_center_deltas = [center_delta(rects[i], rects[i-1]) for i in range(1,len(rects))]

    width_mean = round(np.mean([rect[2] for rect in rects]).tolist())
    height_mean = round(np.mean([rect[3] for rect in rects]).tolist())

    if len(rects) < 6:
        # TODO: infer characters by position
        return rects

    # get mean center delta in two directions
    center_delta_mean = np.mean([center_delta(rects[i], rects[i-1]) for i in range(2,6)], axis=0)
    center_delta_mean[0] *= 1.0   # scale in horizon

    char_width = round(1.25*width_mean)
    char_height = height_mean

    char_center = tuple((np.array(center(rects[0])) - center_delta_mean).tolist())
    char_rect = (round(char_center[0]-char_width/2), round(char_center[1]-char_height/2), char_width, char_height)

    rects.insert(0, char_rect)

    # make rects into image of chars
    def make_img(rect):
        img = image[rect[0]:rect[0]+rect[2],rect[1]:rect[1]+rect[4]]
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        height, width = img.shape[:2]
        if height >= width:
            border_left = int((height - width) / 2)
            border_right = height - width - border_left
            img = cv2.copyMakeBorder(img, 0, 0, border_left, border_right, cv2.BORDER_CONSTANT, 0)
        else:
            border_top = int((width - height) / 2)
            border_bottom = width - height - border_top
            img = cv2.copyMakeBorder(img, border_top, border_bottom, 0, 0, cv2.BORDER_CONSTANT, 0)
        return cv2.resize(img, (20, 20))

    char_imgs = [make_img(rect) for rect in rects]

    return (rects, char_imgs)

def draw_regions(image, rects):
    vis = image.copy()    # for visualization
    for rect in rects:
        cv2.rectangle(vis, (rect[0],rect[1]), (rect[0]+rect[2],rect[1]+rect[3]), (0, 0, 255), 2)
    return vis

if __name__ == '__main__':
    if len(sys.argv) < 2:
        quit()

    minProb1 = float(sys.argv[2]) if len(sys.argv) >= 3 else 0.5
    minProb1 = float(sys.argv[3]) if len(sys.argv) >= 4 else 0.75

    image = cv2.imread(sys.argv[1])
    vis = draw_regions(image, get_chars(image)[1])
    plt.imshow(cv2.cvtColor(vis, cv2.COLOR_BGR2RGB))
    plt.show()