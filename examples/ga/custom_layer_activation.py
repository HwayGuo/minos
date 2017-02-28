'''
Created on Feb 6, 2017

@author: julien
'''

from keras import backend, activations
from keras.engine.topology import Layer

from examples.ga.dataset import get_reuters_dataset
from minos.experiment.experiment import Experiment, ExperimentParameters
from minos.experiment.ga import run_ga_search_experiment
from minos.experiment.training import Training, AccuracyDecreaseStoppingCondition,\
    EpochStoppingCondition
from minos.model.build import ModelBuilder
from minos.model.model import Objective, Optimizer, Metric, Layout
from minos.model.parameter import int_param, string_param, float_param
from minos.model.parameters import register_custom_activation,\
    register_custom_layer
from minos.train.utils import CpuEnvironment, cpu_device, Environment
import numpy as np


np.random.seed(1337)
max_words = 1000


def build_layout(input_size, output_size):
    """ Here we define a minimal layout. We don't specify the architecture.
    Layouts will be randomly generated using the min and max numbers of rows, blocks and layers
    """
    return Layout(
        input_size=input_size,
        output_size=output_size,
        output_activation='softmax')


def custom_activation(x):
    return 1 + backend.tanh(x)


class CustomLayer(Layer):

    def __init__(self, output_dim=None, activation=None, **kwargs):
        self.output_dim = output_dim
        self.activation = activations.get(activation)
        super().__init__(**kwargs)

    def build(self, input_shape):
        self.W = self.add_weight(
            shape=(input_shape[1], self.output_dim),
            initializer='glorot_uniform',
            trainable=True)
        self.b = self.add_weight(
            shape=(self.output_dim,),
            initializer='glorot_uniform',
            trainable=True)
        super().build(input_shape)  # Be sure to call this somewhere!

    def call(self, x, mask=None):
        return self.activation(backend.dot(x, self.W) + self.b)

    def get_output_shape_for(self, input_shape):
        return (input_shape[0], self.output_dim)


def register_custom_definitions():
    register_custom_activation(
        'custom_activation_1',
        custom_activation)
    register_custom_layer(
        'custom_layer_1',
        CustomLayer,
        params={
            'output_dim': int_param(10, 100),
            'activation': 'custom_activation_1'})


def custom_experiment_parameters():
    """ Here we define the experiment parameters.
    We are using use_default_values=True, which will initialize
    all the parameters with their default values. These parameters are then fixed
    for the duration of the experiment and won't evolve.
    That means that we need to manually specify which parametres we want to test,
    and the possible values, either intervals or lists of values.

    If we want to test all the parameters and possible values, we can
    set use_default_values to False. In that case, random values will be generated
    and tested during the experiment. We can redefine some parameters if we want to
    fix their values.
    Reference parameters and default values are defined in minos.model.parameters
    """
    experiment_parameters = ExperimentParameters(use_default_values=True)
    experiment_parameters.layout_parameter('rows', 1)
    experiment_parameters.layout_parameter('blocks', int_param(1, 2))
    experiment_parameters.layout_parameter('layers', int_param(1, 3))
    experiment_parameters.layer_parameter('Dense.output_dim', int_param(10, 100))
    experiment_parameters.layer_parameter('Dense.activation', string_param(['relu', 'custom_activation_1']))
    experiment_parameters.layer_parameter('Dropout.p', float_param(0.1, 0.9))
    return experiment_parameters


def accuracy_decrease_stopping_condition():
    """ This stopping condition lets the training continue as long as the
    accuracy improves and stops if it doesn't improve for 5 epochs
    """
    return AccuracyDecreaseStoppingCondition(
        min_epoch=2,
        max_epoch=10,
        noprogress_count=5)


def epoch_stopping_condition():
    """ This stopping condition lets the training run for 10 epochs
    """
    return EpochStoppingCondition(epoch=10)


def search_model(experiment_label, steps, batch_size=32):
    """ This is where we put everythin together.
    We get the dataset, build the Training and Experiment objects, and run the experiment.
    The experiments logs are generated in ~/minos/experiment_label
    We use the CpuEnvironment to have the experiment run on the cpu, with 2 parralel processes.
    We could use GpuEnvironment to use GPUs, and specify which GPUs to use, and how many tasks
    per GPU
    """
    batch_iterator, test_batch_iterator, nb_classes = get_reuters_dataset(batch_size, max_words)
    layout = build_layout(max_words, nb_classes)
    training = Training(
        Objective('categorical_crossentropy'),
        Optimizer(optimizer='Adam'),
        Metric('categorical_accuracy'),
        epoch_stopping_condition(),
        batch_size)
    parameters = custom_experiment_parameters()
    experiment = Experiment(
        experiment_label,
        layout,
        training,
        batch_iterator,
        test_batch_iterator,
        CpuEnvironment(n_jobs=1),
        parameters=parameters)
    run_ga_search_experiment(
        experiment,
        population_size=100,
        generations=steps,
        resume=False,
        log_level='DEBUG')


def load_best_model(experiment_label, step):
    """ Here we load the blueprints generated during an experiment
    and create the Keras model from the top scoring blueprint
    """
    blueprint = load_experiment_best_blueprint(
        experiment_label,
        step,
        Environment())
    return ModelBuilder().build(
        blueprint,
        cpu_device(),
        compile_model=False)


def main():
    experiment_label = 'reuters_experiment'
    steps = 100
    register_custom_definitions()
    search_model(experiment_label, steps)
    load_best_model(experiment_label, steps - 1)

if __name__ == '__main__':
    main()