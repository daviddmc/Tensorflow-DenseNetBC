# Copyright 2016 The TensorFlow Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
"""
Contains definitions for DenseNets. Based off ResNet models in Tensorflow Slim

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import tensorflow as tf
import math

slim = tf.contrib.slim


def densenet_arg_scope(weight_decay=0.0001,
                       batch_norm_decay=0.997,
                       batch_norm_epsilon=1e-5,
                       batch_norm_scale=True):
    """Defines the default DenseNet arg scope.

    Args:
      weight_decay: The weight decay to use for regularizing the model.
      batch_norm_decay: The moving average decay when estimating layer activation
        statistics in batch normalization.
      batch_norm_epsilon: Small constant to prevent division by zero when
        normalizing activations by their variance in batch normalization.
      batch_norm_scale: If True, uses an explicit `gamma` multiplier to scale the
        activations in the batch normalization layer.

    Returns:
      An `arg_scope` to use for the densenet models.
    """
    batch_norm_params = {
        'decay': batch_norm_decay,
        'epsilon': batch_norm_epsilon,
        'scale': batch_norm_scale,
        'updates_collections': tf.GraphKeys.UPDATE_OPS,
    }

    with slim.arg_scope(
            [slim.conv2d],
            weights_regularizer=slim.l2_regularizer(weight_decay),
            weights_initializer=slim.variance_scaling_initializer(),
            activation_fn=tf.nn.relu,
    ):
        with slim.arg_scope([slim.batch_norm], **batch_norm_params):
            with slim.arg_scope([slim.max_pool2d], padding='SAME') as arg_sc:
                return arg_sc


def densenet_bc(inputs,
                num_classes=None,
                is_training=True,
                growth_rate=12,
                drop_rate=0,
                depth=100,
                for_imagenet=False,
                reuse=None,
                scope=None):
    """Generator for DenseNet models.

    Args:
      inputs: A tensor of size [batch, height_in, width_in, channels].
      num_classes: Number of predicted classes for classification tasks. If None
        we return the features before the logit layer.
      is_training: whether is training or not.
      reuse: whether or not the network and its variables should be reused. To be
        able to reuse 'scope' must be given.
      scope: Optional variable_scope.


    Returns:
      net: A rank-4 tensor of size [batch, height_out, width_out, channels_out].
      end_points: A dictionary from components of the network to the corresponding
        activation.

    Raises:
      ValueError: If the target output_stride is not valid.
    """

    n_channels = 2 * growth_rate
    reduction = 0.5
    bottleneck = True
    N = int((depth - 4) / (6 if bottleneck else 3))

    def single_layer(input, n_out_channels, drop_rate):

        conv = slim.batch_norm(input, activation_fn=tf.nn.relu)
        conv = slim.conv2d(conv, n_out_channels, [3, 3], stride=[1, 1])
        if drop_rate > 0:
            conv = tf.nn.dropout(conv, drop_rate)

        out = tf.concat(3, [tf.identity(input), conv])

        return out

    def bottleneck_layer(input, n_output_channels, drop_rate):

        inter_channels = 4 * n_output_channels

        conv = slim.batch_norm(input, activation_fn=tf.nn.relu)
        conv = slim.conv2d(conv, inter_channels, [1, 1], stride=[1, 1])
        if drop_rate > 0:
            conv = tf.nn.dropout(conv, drop_rate)

        conv = slim.batch_norm(conv, activation_fn=tf.nn.relu)
        conv = slim.conv2d(conv, inter_channels, [3, 3], stride=[1, 1])
        if drop_rate > 0:
            conv = tf.nn.dropout(conv, drop_rate)

        out = tf.concat(3, [tf.identity(input), conv])

        return out

    if bottleneck:
        add = bottleneck_layer
    else:
        add = single_layer

    def transition(input, n_output_channels, drop_rate):

        conv = slim.batch_norm(input, activation_fn=tf.nn.relu)
        conv = slim.conv2d(conv, n_output_channels, [1, 1], stride=[1, 1])
        if drop_rate > 0:
            conv = tf.nn.dropout(conv, drop_rate)
        conv = slim.avg_pool2d(conv, [2, 2], stride=2)

        return conv

    with tf.variable_scope(scope, 'densenet', [inputs], reuse=reuse) as sc:
        end_points_collection = sc.name + '_end_points'
        with slim.arg_scope([slim.conv2d, slim.avg_pool2d],
                            outputs_collections=end_points_collection, padding='SAME'):
            with slim.arg_scope([slim.batch_norm], is_training=is_training):
                net = inputs

                if for_imagenet:
                    net = slim.conv2d(net, n_channels, [7, 7], stride=2)
                    net = slim.max_pool2d(net, [3, 3], stride=2)

                    for i in range(0, 6):
                        net = add(net, growth_rate, drop_rate)
                        n_channels += growth_rate

                    net = transition(net, math.floor(n_channels * reduction), drop_rate)
                    n_channels = math.floor(n_channels * reduction)

                    for i in range(0, 12):
                        net = add(net, growth_rate, drop_rate)
                        n_channels += growth_rate

                    net = transition(net, math.floor(n_channels * reduction), drop_rate)
                    n_channels = math.floor(n_channels * reduction)

                    for i in range(0, 36):
                        net = add(net, growth_rate, drop_rate)
                        n_channels += growth_rate

                    net = transition(net, math.floor(n_channels * reduction), drop_rate)
                    n_channels = math.floor(n_channels * reduction)

                    for i in range(0, 24):
                        net = add(net, growth_rate, drop_rate)
                        n_channels += growth_rate

                    net = slim.batch_norm(net, activation_fn=tf.nn.relu)
                    net = slim.avg_pool2d(net, [7, 7], stride=7)

                else:
                    net = slim.conv2d(net, n_channels, [3, 3], stride=1)

                    for i in range(0, N):
                        net = add(net, growth_rate, drop_rate)
                        n_channels += growth_rate

                    net = transition(net, math.floor(n_channels * reduction), drop_rate)
                    n_channels = math.floor(n_channels * reduction)

                    for i in range(0, N):
                        net = add(net, growth_rate, drop_rate)
                        n_channels += growth_rate

                    net = transition(net, math.floor(n_channels * reduction), drop_rate)
                    n_channels = math.floor(n_channels * reduction)

                    for i in range(0, N):
                        net = add(net, growth_rate, drop_rate)
                        n_channels += growth_rate

                    net = slim.batch_norm(net, activation_fn=tf.nn.relu)
                    net = slim.avg_pool2d(net, [8, 8], stride=8)


                if num_classes is not None:
                    net = slim.conv2d(net, num_classes, [1, 1], activation_fn=None,
                                      normalizer_fn=None, scope='logits')
                net = tf.squeeze(net)
                # Convert end_points_collection into a dictionary of end_points.
                end_points = slim.utils.convert_collection_to_dict(end_points_collection)
                if num_classes is not None:
                    end_points['predictions'] = slim.softmax(net, scope='predictions')
                return net, end_points