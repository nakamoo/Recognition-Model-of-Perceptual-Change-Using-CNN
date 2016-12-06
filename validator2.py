from __future__ import print_function
import argparse
import random

import numpy as np
import matplotlib.pyplot as plt
import os
import cv2 as cv
try:
    import cPickle as pickle
except:
    import pickle
import chainer
from chainer import serializers
from models.attention_model import AttentionModel
from models.VGG import VGG

from utils import imgutil
from utils.ML.data import Data

os.environ['PATH'] += ':/usr/local/cuda-7.5/bin'


class Validator(object):
    def __init__(self, model, data):
        self.model = model
        self.data = data
        vgg = VGG()
        serializers.load_hdf5('VGG.model', vgg)
        self.VGG = vgg

    def validate(self, test=True, attention=False):
        print("start validation!")
        while True:
            if test:
                index = [random.randint(0, data.TEST_N - 1)]
            else:
                index = [random.randint(0, data.N - 1)]

            print("index is " + str(index[0]))

            x_batch, t_batch = self.data.get(index=index, test=test)
            x = chainer.Variable(np.asarray(x_batch))
            if attention:
                a_batch = np.eye(2)[t_batch].astype(np.float32)
                a = chainer.Variable(np.asarray(a_batch))
                fm = self.VGG(x, stop_layer=5)
                pred_t = self.model.forward_with_attention(fm, a).data[0]
            else:
                fm = self.VGG(x, stop_layer=5)
                pred_t = self.model(fm).data[0]

            print("Print t_batch")
            print(t_batch[0])
            print("Print prediction")
            print(pred_t)

            img = x_batch[0] * 255
            plt.imshow(img.astype(np.uint8).transpose(1,2,0))
            plt.show()

            print("Press q to quit.")
            key = raw_input()
            if key == 'q':
                return

    def validate_all(self, test=True, attention=False):
        print("validate all picture!")
        score = 0.0
        if test:
            indexes = range(data.TEST_N)
        else:
            indexes = range(data.N)

        for index in indexes:
            x_batch, t_batch = self.data.get(index=[index], test=test)
            x = chainer.Variable(np.asarray(x_batch))
            if attention:
                a_batch = np.eye(2)[t_batch].astype(np.float32)
                a = chainer.Variable(np.asarray(a_batch))
                fm = self.VGG(x, stop_layer=5)
                pred_t = self.model.forward_with_attention(fm, a).data[0]
            else:
                fm = self.VGG(x, stop_layer=5)
                pred_t = self.model(fm).data[0]

            if t_batch == np.argmax(pred_t):
                score += 1

        print(score / len(indexes))

    def validate_sample(self, test=True, attention=None):
        print("sample image!")
        x = chainer.Variable(sample_im(size=self.data.insize))
        if attention in [0, 1]:
            print(attention)
            t_batch = [[attention]]
            a_batch = np.eye(2)[t_batch].astype(np.float32)
            a = chainer.Variable(np.asarray(a_batch))
            fm = self.VGG(x, stop_layer=5)
            pred_t = self.model.forward_with_attention(fm, a).data[0]
        else:
            fm = self.VGG(x, stop_layer=5)
            pred_t = self.model(fm).data[0]
        print("Print prediction")
        print(pred_t)

    def investigate_feature(self, test=True):
        print("investigate feature!")
        arr0 = np.zeros(512)
        arr1 = np.zeros(512)
        if test:
            indexes = range(data.TEST_N)
        else:
            indexes = range(data.N)

        for index in indexes:
            x_batch, t_batch = self.data.get(index=[index], test=test)
            x = chainer.Variable(np.asarray(x_batch))
            fm = self.VGG(x, stop_layer=5).data[0]
            if t_batch[0] == 0:
                arr0 += np.array([np.average(x) for x in fm])
            elif t_batch[0] == 1:
                arr1 += np.array([np.average(x) for x in fm])
        pass

    def sample_simulate(self):
        print("simulate!")
        result = []

        x = chainer.Variable(sample_im(size=self.data.insize))
        fm = self.VGG(x, stop_layer=5)
        pred_t = self.model(fm).data[0]

        for _ in range(800):
            if pred_t[0] > np.random.rand():
                attention = 0
            else:
                attention = 1

            t_batch = [[attention]]
            a_batch = np.eye(2)[t_batch].astype(np.float32)
            a = chainer.Variable(np.asarray(a_batch))

            fm = self.VGG(x, stop_layer=5)
            pred_t = self.model.forward_with_attention(fm, a).data[0]

            result.append(pred_t.argmax())

        print("simulated!")

        plt.plot(range(1, len(result)+1), result)
        plt.ylim([-0.3, 1.3])
        plt.tick_params(labelleft='off')
        plt.savefig('simulate_double.jpg')

        print(result)


def sample_im(size=256):
    """Return a preprocessed (averaged and resized to VGG) sample image."""
    # mean = np.array([103.939, 116.779, 123.68])
    im = cv.imread('images/double.jpg').astype(np.float32)
    # im -= mean
    im = cv.resize(im, (size, size)).transpose((2, 0, 1))
    im = im[np.newaxis, :, :, :] / 255.0
    return im


if __name__ == '__main__':
    # parse args
    parser = argparse.ArgumentParser(description='yuragi')
    parser.add_argument('model', type=str)
    parser.add_argument('--use_train_data', action='store_true')
    parser.add_argument('--no_attention', action='store_true')
    args = parser.parse_args()

    test = not args.use_train_data

    # make model.
    print(args.model)
    model = AttentionModel()
    serializers.load_npz(args.model, model)
    if not model._cpu:
        model.to_cpu()
    model.train = False

    # set hyper param and data.
    data = Data(k=5, insize=224)

    validator = Validator(model, data)
    # validator.validate_all(test=test)
    # validator.validate_sample(test=test)
    # validator.validate(test=test)
    # validator.investigate_feature(test=test)
    validator.sample_simulate()
    if not args.no_attention:
        print("Use attention!")
        # validator.validate_all(test=test, attention=True)
        # validator.validate(test=test, attention=True)
        # validator.validate_sample(test=test, attention=0)
        # validator.validate_sample(test=test, attention=1)


