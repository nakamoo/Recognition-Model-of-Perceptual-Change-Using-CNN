from __future__ import print_function
import argparse
import random

import numpy as np
import matplotlib.pyplot as plt
import os
try:
    import cPickle as pickle
except:
    import pickle
import chainer
from chainer import cuda

from utils.ML.data import Data
from utils import imgutil

os.environ['PATH'] += ':/usr/local/cuda-7.5/bin'


class Validator(object):
    def __init__(self, model, data):
        self.model = model
        self.data = data

    def validate(self, test=True):
        while True:
            if test:
                index = [random.randint(0, data.TEST_N - 1)]
            else:
                index = [random.randint(0, data.N - 1)]

            print("index is " + str(index[0]))

            x_batch, t_batch = self.data.get(index=index, test=test)
            x = chainer.Variable(np.asarray(x_batch))
            pred_t = self.model(x).data[0]

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


if __name__ == '__main__':
    # parse args
    parser = argparse.ArgumentParser(description='yuragi')
    parser.add_argument('model', type=str)
    parser.add_argument('--test', default=True)
    args = parser.parse_args()

    # make model.
    print(args.model)
    model = pickle.load(open(args.model, 'r'))
    if not model._cpu:
        model.to_cpu()
    model.train = False

    # set hyper param and data.
    data = Data()

    validator = Validator(model, data)
    validator.validate(test=args.test)


