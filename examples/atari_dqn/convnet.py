import numpy as np
import tensorflow as tf


class ConvNet:
    def __init__(self, name, folder_name=None, load_path=None, **convnet_pars):
        self._name = name

        self._session = tf.Session()

        if load_path is not None:
            self._load(load_path)
        else:
            self._build(convnet_pars)

        if self._name == 'train':
            self._folder_name = folder_name
            self._train_writer = tf.summary.FileWriter(
                self._folder_name,
                graph=tf.get_default_graph()
            )

            self._train_saver = tf.train.Saver()

    def predict(self, x):
        if isinstance(x, list):
            return self._session.run(
                self._q_acted, feed_dict={self._x: x[0],
                                          self._action: x[1].ravel().astype(
                                              np.uint8)})
        return self._session.run(self.q, feed_dict={self._x: x})

    def train_on_batch(self, x, y):
        summaries, _ = self._session.run(
            [self._merged, self._train_step],
            feed_dict={self._x: x[0],
                       self._action: x[1].ravel().astype(np.uint8),
                       self._target_q: y}
        )
        self._train_writer.add_summary(summaries, self._train_count)

        self._train_count += 1

    def set_weights(self, weights):
        w = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES,
                              scope=self._name)
        assert len(w) == len(weights)

        for i in xrange(len(w)):
            self._session.run(tf.assign(w[i], weights[i]))

    def get_weights(self):
        w = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES,
                              scope=self._name)

        return self._session.run(w)

    def save(self):
        self._train_saver.save(
            self._session,
            self._folder_name + '/dqn'
        )

    def _load(self, path):
        restorer = tf.train.import_meta_graph(path + 'dqn.meta')
        restorer.restore(self._session, path + 'dqn')
        self._restore_collection()

    def _build(self, convnet_pars):
        with tf.variable_scope(self._name):
            self._x = tf.placeholder(tf.float32,
                                     shape=[None,
                                            convnet_pars['height'],
                                            convnet_pars['width'],
                                            convnet_pars['history_length']],
                                     name='input')
            hidden_1 = tf.layers.conv2d(
                self._x, 32, 8, 4, activation=tf.nn.relu,
                kernel_initializer=tf.glorot_uniform_initializer(),
                bias_initializer=tf.glorot_uniform_initializer(),
                name='hidden_1'
            )
            hidden_2 = tf.layers.conv2d(
                hidden_1, 64, 4, 2, activation=tf.nn.relu,
                kernel_initializer=tf.glorot_uniform_initializer(),
                bias_initializer=tf.glorot_uniform_initializer(),
                name='hidden_2'
            )
            hidden_3 = tf.layers.conv2d(
                hidden_2, 64, 3, 1, activation=tf.nn.relu,
                kernel_initializer=tf.glorot_uniform_initializer(),
                bias_initializer=tf.glorot_uniform_initializer(),
                name='hidden_3'
            )
            flatten = tf.reshape(hidden_3, [-1, 7 * 7 * 64], name='flatten')
            features = tf.layers.dense(
                flatten, 512, activation=tf.nn.relu,
                kernel_initializer=tf.glorot_uniform_initializer(),
                bias_initializer=tf.glorot_uniform_initializer(),
                name='features'
            )
            self.q = tf.layers.dense(
                features, convnet_pars['n_actions'],
                kernel_initializer=tf.glorot_uniform_initializer(),
                bias_initializer=tf.glorot_uniform_initializer(),
                name='q'
            )

            self._target_q = tf.placeholder('float32', [None], name='target_q')
            self._action = tf.placeholder('uint8', [None], name='action')

            with tf.name_scope('gather'):
                action_one_hot = tf.one_hot(self._action,
                                            convnet_pars['n_actions'],
                                            name='action_one_hot')
                self._q_acted = tf.reduce_sum(self.q * action_one_hot,
                                              axis=1,
                                              name='q_acted')

            loss = tf.losses.huber_loss(self._target_q, self._q_acted)
            tf.summary.scalar('huber_loss', loss)
            tf.summary.scalar('average_q', tf.reduce_mean(self.q))
            self._merged = tf.summary.merge_all()

            optimizer = convnet_pars['optimizer']
            if optimizer['name'] == 'rmspropcentered':
                opt = tf.train.RMSPropOptimizer(learning_rate=optimizer['lr'],
                                                decay=optimizer['decay'],
                                                centered=True)
            elif optimizer['name'] == 'rmsprop':
                opt = tf.train.RMSPropOptimizer(learning_rate=optimizer['lr'],
                                                decay=optimizer['decay'])
            elif optimizer['name'] == 'adam':
                opt = tf.train.AdamOptimizer()
            elif optimizer['name'] == 'adadelta':
                opt = tf.train.AdadeltaOptimizer()
            else:
                raise ValueError('Unavailable optimizer selected.')

            self._train_count = 0
            self._train_step = opt.minimize(loss=loss)

        self._session.run(tf.global_variables_initializer())

        self._add_collection()

    def _add_collection(self):
        tf.add_to_collection('x', self._x)
        tf.add_to_collection('action', self._action)
        tf.add_to_collection('q', self.q)
        tf.add_to_collection('target_q', self._target_q)
        tf.add_to_collection('q_acted', self._q_acted)
        tf.add_to_collection('merged', self._merged)
        tf.add_to_collection('train_step', self._train_step)

    def _restore_collection(self):
        self._x = tf.get_collection('x')[0]
        self._action = tf.get_collection('action')[0]
        self.q = tf.get_collection('q')[0]
        self._target_q = tf.get_collection('target_q')[0]
        self._q_acted = tf.get_collection('q_acted')[0]
        self._merged = tf.get_collection('merged')[0]
        self._train_step = tf.get_collection('train_step')[0]