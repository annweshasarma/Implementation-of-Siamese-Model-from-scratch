import sys
import numpy as np
import pandas as pd
import pickle
import os
import imageio

import matplotlib.pyplot as plt




import time

import tensorflow as tf
from keras.models import Sequential
from keras.optimizers import Adam
from keras.layers import Conv2D, ZeroPadding2D, Activation, Input, concatenate
from keras.models import Model
from keras.engine import Input

from keras.layers.normalization import BatchNormalization
from keras.layers.pooling import MaxPooling2D
from keras.layers.merge import Concatenate
from keras.layers.core import Lambda, Flatten, Dense
from keras.initializers import glorot_uniform,RandomNormal


from keras.engine.topology import Layer
from keras.regularizers import l2
from keras import backend as K

from sklearn.utils import shuffle

import numpy.random as rng

from tensorflow.python.client import device_lib



training_datadir = r"C:\Users\KIIT\Downloads\omniglot\omniglot\images_background"
validation_datadir = r"C:\Users\KIIT\Downloads\omniglot\omniglot\images_evaluation"
saved_path = r"C:\Users\KIIT\Downloads\omniglot\omniglot"


def loads(path , n=0):
    X=[]
    y=[]
    lang_dict={}
    cat_dict={}
    curr_y=n
    
    for alphabet in os.listdir(path):
        print("loading alphabet: " + alphabet)
        lang_dict[alphabet] = [curr_y,None]
        alphabet_path = os.path.join(path,alphabet)
        
        
        for letter in os.listdir(alphabet_path):
            cat_dict[curr_y] = (alphabet, letter)
            category_images=[]
            letter_path = os.path.join(alphabet_path, letter)
            
           
            for filename in os.listdir(letter_path):
                image_path = os.path.join(letter_path, filename)
                image = imageio.imread(image_path)
                category_images.append(image)
                y.append(curr_y)
                
            try:
                X.append(np.stack(category_images))
                
            except ValueError as e:
                print(e)
                print("error - category_images:", category_images)
            curr_y=curr_y+1
            lang_dict[alphabet][1]=curr_y-1
    y = np.vstack(y)
    X = np.stack(X)
    return X,y,lang_dict


    X,y,c=loads(training_datadir)

    with open(os.path.join(saved_path,"training.pickle"),"wb") as f:
    pickle.dump((X,c),f)


Xval,Ycal,Cval = loads(validation_datadir)

with open(os.path.join(saved_path,"validation.pickle"), "wb") as f:
    pickle.dump((Xval,Cval),f)


def initialize_weights(shape , name= None , dtype='float32'):
    return K.random_normal(shape , mean=0.0 , stddev=0.01, dtype= dtype)
def initialize_bias(shape , name= None , dtype='float32'):
    return K.random_normal(shape , mean=0.0 , stddev=0.01, dtype= dtype)


def siamese(input_shape):
    left_inp= Input(input_shape)
    right_inp=Input(input_shape)
    
    model = Sequential()
    model.add(Conv2D(64, (10,10), activation='relu', input_shape=input_shape,
                   kernel_initializer=initialize_weights, kernel_regularizer=l2(2e-4)))
    model.add(MaxPooling2D())
    model.add(Conv2D(128, (7,7), activation='relu',
                     kernel_initializer=initialize_weights,
                     bias_initializer=initialize_bias, kernel_regularizer=l2(2e-4)))
    model.add(MaxPooling2D())
    model.add(Conv2D(128, (4,4), activation='relu', kernel_initializer=initialize_weights,
                     bias_initializer=initialize_bias, kernel_regularizer=l2(2e-4)))
    model.add(MaxPooling2D())
    model.add(Conv2D(256, (4,4), activation='relu', kernel_initializer=initialize_weights,
                     bias_initializer=initialize_bias, kernel_regularizer=l2(2e-4)))
    model.add(Flatten())
    model.add(Dense(4096, activation='sigmoid',
                   kernel_regularizer=l2(1e-3),
                   kernel_initializer=initialize_weights,bias_initializer=initialize_bias))

    
    left_encode= model(left_inp)
    right_encode= model( right_inp)
    
    L1_layer = Lambda(lambda tensors:K.abs(tensors[0] - tensors[1]))
    L1_distance = L1_layer([left_encode, right_encode])
    
    prediction= Dense(1 , activation ='sigmoid', bias_initializer=initialize_bias)(L1_distance)
    
    siamese_network = Model(inputs=[left_inp,right_inp] , outputs = prediction)
    
    return siamese_network

model = siamese((105, 105, 1))
model.summary()



optimizer= Adam(learning_rate=0.00006)
model.compile(optimizer=optimizer , loss="binary_crossentropy")

with open(os.path.join(saved_path, "training.pickle"), "rb") as f:
    (Xtrain, train_classes) = pickle.load(f)

print("Training alphabets: \n")
print(list(train_classes.keys()))
print(Xtrain.shape)
    
with open(os.path.join(saved_path,"validation.pickle"),"rb") as f:
    (Xval,val_classes) = pickle.load(f)

print("Validation alphabet: \n")
print(list(val_classes.keys()))
print(Xval.shape)


def get_batch(batch_size, s='train'):
    if s == 'train':
        X = Xtrain
        categories = train_classes
    else:
        X = Xval
        categories = val_classes
    n_classes, n_examples, w, h = X.shape
    
    categories=rng.choice(n_classes, size=(batch_size), replace=False)
    
    pairs=[np.zeros((batch_size, w, h ,1)) for i in range (2)]
    
    targets=np.zeros((batch_size,))
    
    targets[batch_size//2:]=1
    for i in range (batch_size):
        category=categories[i]
        index_1= rng.randint(0, n_examples)
        pairs[0][i,:,:,:]=X[category, index_1].reshape(w, h, 1)
        index_2 = rng.randint(0, n_examples)

        if i>=batch_size//2:
            category_2 = category
        else:
           
            category_2 = (category + rng.randint(1,n_classes)) % n_classes

        pairs[1][i,:,:,:] = X[category_2,index_2].reshape(w, h,1)
    
    return pairs,targets

def generate(batch_size,s="train"):
        while True:
            pairs,targets = get_batch(batch_size,s)
            yield(pairs,targets)
        
def oneshot(N,s="val",language=None):
    if s == 'train':

        X = Xtrain
        categories = train_classes
    else:
        X = Xval
        categories = val_classes
    n_classes, n_examples, w, h = X.shape

    indices = rng.randint(0,n_examples,size=(N,))

    if language is not None:
        low, high = categories[language]
        if N > high - low:
            raise ValueError("This language ({}) has less than {} letters".format(language, N))
        categories = rng.choice(range(low,high),size=(N,),replace=False)

    else: 
        categories = rng.choice(range(n_classes),size=(N,),replace=False)            
    
    true_category = categories[0]
    ex1, ex2 = rng.choice(n_examples,replace=False,size=(2,))
    test_image = np.asarray([X[true_category,ex1,:,:]]*N).reshape(N, w, h,1)
    support_set = X[categories,indices,:,:]
    support_set[0,:,:] = X[true_category,ex2]
    support_set = support_set.reshape(N, w, h,1)
    targets = np.zeros((N,))
    targets[0] = 1
    targets, test_image, support_set = shuffle(targets, test_image, support_set)
    pairs = [test_image,support_set]


def test_oneshot(model, N, k, s = "val", verbose = 0):
    
    n_correct = 0
    if verbose:
        print("Evaluating model on {} random {} way one-shot learning tasks ... \n".format(k,N))
    for i in range(k):
        inputs, targets =oneshot(N,s)
        probs = model.predict(inputs)
        if np.argmax(probs) == np.argmax(targets):
            n_correct+=1
    percent_correct = (100.0 * n_correct / k)
    if verbose:
        print("Got an average of {}% {} way one-shot learning accuracy \n".format(percent_correct,N))
    return percent_correct


    evaluate_every = 200 # interval for evaluating on one-shot tasks
batch_size = 32
n_iter = 20000 # No. of training iterations
N_way = 20 # how many classes for testing one-shot tasks
n_val = 250 # how many one-shot tasks to validate on
best = -1

model_path = saved_path

print("Starting training process!")
print("-------------------------------------")
t_start = time.time()
for i in range(1, n_iter+1):
    inputs,targets = get_batch(batch_size)
    loss = model.train_on_batch(inputs, targets)
    if i % evaluate_every == 0:
        print("\n ------------- \n")
        print("Time for {0} iterations: {1} mins".format(i, (time.time()-t_start)/60.0))
        print("Train Loss: {0}".format(loss)) 
        val_acc = test_oneshot(model, N_way, n_val, verbose=True)
        model.save_weights(os.path.join(model_path, 'weights.{}.h5'.format(i)))
        if val_acc >= best:
            print("Current best: {0}, previous best: {1}".format(val_acc, best))
            best = val_acc
