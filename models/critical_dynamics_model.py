import chainer
import chainer.links as L
import chainer.functions as F
from chainer import Variable
import numpy as np
from lib.chainer.chainer.functions.pooling import max_pooling_2d
from lib.chainer.chainer.functions.pooling import unpooling_2d

# Override original Chainer functions
# F.max_pooling_2d = max_pooling_2d.max_pooling_2d
# F.unpooling_2d = unpooling_2d.unpooling_2d


class CriticalDynamicsModel(chainer.Chain):
    """Input dimensions are (128, 128)."""
    def __init__(self, nobias=True):
        super(CriticalDynamicsModel, self).__init__(
            conv1_1=L.Convolution2D(3, 64, 3, stride=1, nobias=nobias, pad=1),
            conv1_2=L.Convolution2D(64, 64, 3, stride=1, nobias=nobias, pad=1),
            conv2_1=L.Convolution2D(64, 64, 3, stride=1, nobias=nobias, pad=1),
            conv2_2=L.Convolution2D(64, 64, 3, stride=1, nobias=nobias, pad=1),
            conv3_1=L.Convolution2D(64, 64, 3, stride=1, nobias=nobias, pad=1),
            conv3_2=L.Convolution2D(64, 32, 3, stride=1, nobias=nobias, pad=1),
            attention=L.Linear(2, 16384),
            fc6=L.Linear(16384, 2),
        )
        self.convs = [
            ['conv1_1', 'conv1_2'],
            ['conv2_1', 'conv2_2'],
            ['conv3_1', 'conv3_2'],
        ]

        self.train = False
        self.added_deconv = False
        self.unpooling_outsizes = []
        self.added_deconv = False

    def __call__(self, x, t=None, stop_layer=None):
        self.switches = []
        self.unpooling_outsizes = []

        # Forward pass through convolutional layers with ReLU and pooling
        h = x
        for i, layer in enumerate(self.convs):
            for conv in layer:
                h = F.relu(getattr(self, conv)(h))

            if self.train:
                h = F.max_pooling_2d(h, 2, stride=2)
            else:
                prepooling_size = h.data.shape[2:]
                self.unpooling_outsizes.append(prepooling_size)
                h, switches = max_pooling_2d.max_pooling_2d(h, 2, stride=2)
                self.switches.append(switches)

            if stop_layer == i + 1:
                return h

        h = self.fc6(h)

        if self.train:
            self.loss = F.softmax_cross_entropy(h, t)
            self.acc = F.accuracy(h, t)
            return self.loss
        else:
            self.pred = F.softmax(h)
            return self.pred

    def forward_with_attention(self, x, a, t=None, stop_layer=None):
        self.switches = []
        self.unpooling_outsizes = []

        # Forward pass through convolutional layers with ReLU and pooling
        h = x
        for i, layer in enumerate(self.convs):
            for conv in layer:
                h = F.relu(getattr(self, conv)(h))

            if self.train:
                h = F.max_pooling_2d(h, 2, stride=2)
            else:
                prepooling_size = h.data.shape[2:]
                self.unpooling_outsizes.append(prepooling_size)
                h, switches = max_pooling_2d.max_pooling_2d(h, 2, stride=2)
                self.switches.append(switches)

            if stop_layer == i + 1:
                return h

        shape = h.data.shape
        h = F.reshape(h, (h.data.shape[0], 8192))

        attention = F.sigmoid(self.attention(a))

        h = attention * h
        if stop_layer == 'attention':
            h = F.reshape(h, shape)
            return h

        h = self.fc6(h)
        if self.train:
            self.loss = F.softmax_cross_entropy(h, t)
            self.acc = F.accuracy(h, t)
            return self.loss
        else:
            self.pred = F.softmax(h)
            return self.pred

    def activate_with_attention(self, x, a):
        if x.data.shape[0] != 1:
            raise TypeError('Visualization is only supported for a single \
                            image at a time')
        self.add_deconv_layers()
        # Forward pass
        h = self.forward_with_attention(x, a, stop_layer='attention')
        # h = self.forward_with_attention(x, a, stop_layer=3)
        xp = chainer.cuda.get_array_module(h.data)
        layer = len(self.convs)
        deconvs = [['de{}'.format(c) for c in conv] for conv in self.convs]

        feat_maps = []

        for i, deconv in enumerate(reversed(deconvs)):
            h = unpooling_2d.unpooling_2d(h, self.switches[layer-i-1], 2, stride=2,
                               outsize=self.unpooling_outsizes[layer-i-1])
            for d in reversed(deconv):
                h = getattr(self, d)(F.relu(h))

        feat_maps.append(h.data)
        feat_maps = xp.array(feat_maps)
        feat_maps = xp.rollaxis(feat_maps, 0, 2)  # Batch to first axis

        return Variable(feat_maps)

    def activations(self, x, layer):
        if x.data.shape[0] != 1:
            raise TypeError('Visualization is only supported for a single \
                            image at a time')

        self.add_deconv_layers()

        # Forward pass
        h = self(x, stop_layer=layer)

        # Compute the activations for each feature map
        h_data = h.data.copy()
        xp = chainer.cuda.get_array_module(h.data)
        zeros = xp.zeros_like(h.data)
        convs = self.convs[:layer]
        deconvs = [['de{}'.format(c) for c in conv] for conv in convs]

        feat_maps = []

        for fm in range(h.data.shape[1]):  # For each feature map

            print('Feature map {}'.format(fm))

            condition = zeros.copy()
            condition[0][fm] = 1  # Keep one feature map and zero all other
            h = Variable(xp.where(condition, h_data, zeros))

            for i, deconv in enumerate(reversed(deconvs)):
                h = unpooling_2d.unpooling_2d(h, self.switches[layer-i-1], 2, stride=2,
                                   outsize=self.unpooling_outsizes[layer-i-1])
                for d in reversed(deconv):
                    h = getattr(self, d)(F.relu(h))

            feat_maps.append(h.data)

        # h = Variable(h_data)
        # for i, deconv in enumerate(reversed(deconvs)):
        #     # h = F.unpooling_2d(h, self.switches[layer-i-1], 2, stride=2,
        #     #                    outsize=self.unpooling_outsizes[layer-i-1])
        #     for d in reversed(deconv):
        #         h = F.clip(h, 0.0001, 0.9999)
        #         h = getattr(self, d)(F.log(h/(1-h)))
        #         # h = getattr(self, d)(F.relu(h))

        feat_maps = xp.array(feat_maps)
        feat_maps = xp.rollaxis(feat_maps, 0, 2)  # Batch to first axis

        return Variable(feat_maps)

    def add_deconv_layers(self, nobias=True):
        """Add a deconvolutional layer for each convolutional layer already
        defined in the network."""
        if self.added_deconv:
            return

        for layer in self.children():
            if isinstance(layer, F.Convolution2D):
                out_channels, in_channels, kh, kw = layer.W.data.shape
                deconv = L.Deconvolution2D(out_channels, in_channels,
                                           (kh, kw), stride=layer.stride,
                                           pad=layer.pad,
                                           initialW=layer.W.data,
                                           nobias=nobias)
                self.add_link('de{}'.format(layer.name), deconv)

        self.added_deconv = True
