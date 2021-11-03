'''
prefetchDataset shapes: {image: (1, 512, 224, 224, 3), label: (1, 512, 10)}, types: {image: tf.float32, label: tf.float32}

'''

from os import name
import ml_collections
import tensorflow as tf
import tensorflow_addons as tfa
import math

from net.vit import ViT
from dataloader import get_data_from_tfds, get_dataset_info

from SAM import dual_vector

import training_config
import model_config

class With_SAM_Model(tf.keras.Model):
    def __init__(self, inputs, outputs , dual_vector, rho):
        super(With_SAM_Model, self).__init__(inputs,outputs)
        self.dual_vector_fn = dual_vector
        self.rho = rho

    
    def get_sam_gradient(self, grads, x, y):

        grads = dual_vector(grads)

        inner_trainable_vars = self.trainable_variables
        # print(type(self.trainable_variables))
        # print(type(grads))
        # import pdb
        # pdb.set_trace()

        _ = tf.nest.map_structure(lambda a, b: a.assign(a + self.rho * b), self.trainable_variables , grads) # model to noised model

        with tf.GradientTape() as noised_tape:
            noised_y_pred = self(x)  # Forward pass
            noised_loss = self.compiled_loss(y, noised_y_pred)
        
        noised_vars = self.trainable_variables
        noised_grads = noised_tape.gradient(noised_loss, noised_vars)

        _ = tf.nest.map_structure(lambda a, b: a.assign(b), self.trainable_variables, inner_trainable_vars) # noised model to model

        return noised_grads




    def train_step(self, data):
        # Unpack the data. Its structure depends on your model and
        # on what you pass to `fit()`.
        x, y = data


        with tf.GradientTape() as tape:

            
            y_pred = self(x)  # Forward pass
            # Compute the loss valuese
            # (the loss function is configured in `compile()`)
            loss = self.compiled_loss(y, y_pred)

        # Compute gradients
        trainable_vars = self.trainable_variables
        gradients = tape.gradient(loss, trainable_vars)

        noised_grads = self.get_sam_gradient(gradients, x, y)



        # Update weights
        self.optimizer.apply_gradients(zip(gradients, self.trainable_variables))
        # Update metrics (includes the metric that tracks the loss)
        self.compiled_metrics.update_state(y, y_pred)
        # Return a dict mapping metric names to current value
        return {m.name: m.result() for m in self.metrics}


if __name__ == "__main__":
    tf.config.experimental_run_functions_eagerly(True)

    gpus = tf.config.experimental.list_physical_devices('GPU')
    if gpus:
        # Currently, memory growth needs to be the same across GPUs
        for gpu in gpus:
            tf.config.experimental.set_memory_growth(gpu, True)


    # initialize dataset
    dataset = "cifar10"
    
    config = training_config.with_dataset(training_config.get_config(), dataset)
    ds_train_info = get_dataset_info(dataset, "train")
    ds_train_num_classes = ds_train_info['num_classes']
    ds_train_num_examples = ds_train_info["num_examples"]
    ds_train = get_data_from_tfds(config=config, mode='train')

    ds_val_info = get_dataset_info(dataset, "test")
    ds_val_num_classes = ds_train_info['num_classes']
    ds_val_num_examples = ds_train_info["num_examples"]
    ds_val = get_data_from_tfds(config=config, mode='test')


    one_train_data = next(ds_train.as_numpy_iterator())[0]
    print("one_train_data.shape:", one_train_data["image"].shape) # vit_model_config 
    print(one_train_data["image"].shape[1:])


    # initialize model
    vit_model_config = model_config.get_b32_config()
    print(vit_model_config )
    
    vit_model = ViT(num_classes=ds_train_num_classes, **vit_model_config)

    

    # this init the model and avoid manipulate weight in graph(if using resnet)
    trial_logit = vit_model(one_train_data["image"], train = True) # (512, 10) 

    # for varb in vit_model.trainable_variables:
    #     if "kernel" or "bias" in varb.name:
    #         print("varb name:", varb.name)
    #         print("varb.shape:", varb.shape)
    
    # vit_varb = vit_model.trainable_variables

    # vit_varb[0] = vit_varb[0]*0
    
    # for new_varb, origin_varib in zip(vit_varb, vit_model.trainable_variables):
    #     origin_varib.assign(new_varb)

    # print("vit_varb[0]:",vit_varb[0])
    # print("vit_model.trainable_variables:",vit_model.trainable_variables[0])

    # build model, expose this to show how to deal with dict as fit() input
    model_input = tf.keras.Input(shape=one_train_data["image"].shape[1:],name="image",dtype=tf.float32)

    logit = vit_model(model_input)

    
    # logit = sam_model(model_input)

    prob = tf.keras.layers.Softmax(axis = -1, name = "label")(logit)

    # model = tf.keras.Model(inputs = [model_input],outputs = [logit], name = "ViT_model")

    sam_model = With_SAM_Model(inputs = [model_input],outputs = [prob], dual_vector = dual_vector, rho = 0.05)

    model = sam_model



    '''
    the training config is for fine tune. I use my own config instead for training purpose.
    
    '''
    # my training config:
    steps_per_epoch = ds_train_num_examples//config.batch
    validation_steps = 3
    log_dir="./tf_log/"
    total_steps = 100
    warmup_steps = 5
    base_lr = 1e-3

    # define callback 
    tensorboard_callback = tf.keras.callbacks.TensorBoard(log_dir=log_dir, histogram_freq=1)
    save_model_callback = tf.keras.callbacks.ModelCheckpoint(
        filepath='./model/ViT.ckpt',
        save_weights_only= True,
        verbose=1)

    callback_list = [tensorboard_callback,save_model_callback]


    # lr_schedule = tf.keras.optimizers.schedules.ExponentialDecay(initial_learning_rate = 1e-2, decay_steps = 1000, decay_rate = 0.01, staircase=False, name=None)
    # lr_schedule = Cosine_Decay_with_Warm_up(base_lr, total_steps, warmup_steps)


    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate = base_lr), 
        loss={"label":tf.keras.losses.CategoricalCrossentropy(from_logits=False)},
        metrics={'label': 'accuracy'}
        )

    # print(model.summary())

    # import pdb
    # pdb.set_trace()

    hist = model.fit(ds_train,
                epochs=200, 
                steps_per_epoch=steps_per_epoch,
                validation_data = ds_val,
                validation_steps=3,callbacks = callback_list).history

