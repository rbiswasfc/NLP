
#################################################
### THIS FILE WAS AUTOGENERATED! DO NOT EDIT! ###
#################################################
# file to edit: dev_nb/Q4-vf.ipynb
# basic packages
import time
import random
import pickle
import pandas as pd
import matplotlib.pyplot as plt
from IPython.core.debugger import set_trace

# Keras preprocessing
from keras.preprocessing import text, sequence

# Pytorch
import torch
import torch.nn as nn
import torch.nn.functional as F

# Fastai
from fastai.train import Learner
from fastai.train import DataBunch
from fastai.callbacks import *

# sklearn
from sklearn.model_selection import train_test_split

## Set seed for reproducing experiment results

def seed_everything(seed=1234):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.backends.cudnn.deterministic = True

seed = 9461
seed_everything(seed)


def read_corpus(file_path):
    """
    read examples form the given dataset
    """
    data = []
    for line in open(file_path):
        chars = [char for char in line.strip()]
        #  Append <s> and </s> to the  sentence

        sent = ['<s>'] + chars + ['</s>']
        data.append(sent)

    return data


# load data
X_train_path = 'xtrain_obfuscated.txt'
y_train_path = 'ytrain.txt'
X_test_path = 'xtest_obfuscated.txt'

X = read_corpus(X_train_path)
y = np.loadtxt(y_train_path)
X_test = read_corpus(X_test_path)

# set maximum length for analysis
MAX_LEN = 454

# Note: 20% of train data is set aside as validation
# Since train size is small, model can benefit from k-fold cross validation
X_train, X_valid, y_train, y_valid = train_test_split(X, y, test_size=0.2, stratify=y, random_state=seed)

# a-z and <s> + </s>

max_features = 28
# tokenizer
tokenizer = text.Tokenizer(num_words = max_features, filters='',lower=True)
tokenizer.fit_on_texts(list(X_train) + list(X_test) + list(X_valid))

X_train = tokenizer.texts_to_sequences(X_train)
X_valid = tokenizer.texts_to_sequences(X_valid)
X_test = tokenizer.texts_to_sequences(X_test)


X_train_padded = sequence.pad_sequences(X_train, maxlen=MAX_LEN)
X_valid_padded = sequence.pad_sequences(X_valid, maxlen=MAX_LEN)
X_test_padded = sequence.pad_sequences(X_test, maxlen=MAX_LEN)

x_train_torch = torch.tensor(X_train_padded, dtype=torch.long)
y_train_torch = torch.tensor(y_train, dtype=torch.long)

x_valid_torch = torch.tensor(X_valid_padded, dtype=torch.long)
y_valid_torch = torch.tensor(y_valid, dtype=torch.long)

x_test_torch = torch.tensor(X_test_padded, dtype=torch.long)


# dropout
class SpatialDropout(nn.Dropout2d):
    def forward(self, x):
        x = x.unsqueeze(2)    # (N, T, 1, K)
        x = x.permute(0, 3, 2, 1)  # (N, K, 1, T)
        x = super(SpatialDropout, self).forward(x)  # (N, K, 1, T), some features are masked
        x = x.permute(0, 3, 2, 1)  # (N, T, 1, K)
        x = x.squeeze(2)  # (N, T, K)
        return x

# embedding initialization
class ModelEmbedding(nn.Module):

    def __init__(self, max_features, embed_size, dropout = 0.3):

        super(ModelEmbedding, self).__init__()

        self.max_features = max_features
        self.embed_size = embed_size

        self.LUT = nn.Embedding(max_features, embed_size)
        self.LUT_dropout = SpatialDropout(dropout)

        #self.dropout = nn.Dropout(dropout)

    def forward(self, x):

        h_embedding = self.LUT(x)
        h_embedding = self.LUT_dropout(h_embedding)

        return h_embedding

# LSTM Model

class NeuralNet(nn.Module):

  """ LSTM model for author classification

  embed_size: vector dimension for representing chars [default: 50 (should be less than size of word embeddings)]
  LSTM_UNITS: number of hidden units for LSTM layes
  DENSE_HIDDEN_UNITS: hidden units for feed forward layers after amx and average pooling the lstm output
  num_targets: number of authors (default: 12)
  """

  def __init__(self, embed_size, LSTM_UNITS, DENSE_HIDDEN_UNITS, num_targets=12):

      super(NeuralNet, self).__init__()

      # attributes
      self.num_targets = num_targets

      # layers
      self.lstm1 = nn.LSTM(embed_size, LSTM_UNITS, bidirectional=True, batch_first=True)
      self.lstm2 = nn.LSTM(LSTM_UNITS * 2, LSTM_UNITS, bidirectional=True, batch_first=True)
      self.linear1 = nn.Linear(DENSE_HIDDEN_UNITS, DENSE_HIDDEN_UNITS)
      self.linear2 = nn.Linear(DENSE_HIDDEN_UNITS, DENSE_HIDDEN_UNITS)
      self.linear_out = nn.Linear(DENSE_HIDDEN_UNITS, num_targets)


  def forward(self, h_embedding, lengths=None):

      "Takes input char sequence and predict output logits"

      #set_trace()
      h_lstm1, _ = self.lstm1(h_embedding)
      h_lstm2, _ = self.lstm2(h_lstm1)

      # global average pooling
      avg_pool = torch.mean(h_lstm2, 1)
      # global max pooling
      max_pool, _ = torch.max(h_lstm2, 1)

      h_conc = torch.cat((max_pool, avg_pool), 1)
      h_conc_linear1  = F.relu(self.linear1(h_conc))
      h_conc_linear2  = F.relu(self.linear2(h_conc))

      hidden = h_conc + h_conc_linear1 + h_conc_linear2

      result = self.linear_out(hidden) # logits before cross-entrophy


      return result


# combine embedding and neuralnet

class LSTM_model(nn.Module):

    def __init__(self, LUT, NeuralNet):

        super(LSTM_model, self).__init__()
        self.LUT = LUT
        self.Net = NeuralNet

    def forward(self, x, lengths=None):

        h_embedding = self.LUT(x.long())
        out = self.Net(h_embedding)

        return out


# prepare train data
batch_size = 64

train_dataset = torch.utils.data.TensorDataset(x_train_torch, y_train_torch)
valid_dataset = torch.utils.data.TensorDataset(x_valid_torch, y_valid_torch)
test_dataset = torch.utils.data.TensorDataset(x_test_torch)

train_loader = torch.utils.data.DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
valid_loader = torch.utils.data.DataLoader(valid_dataset, batch_size=batch_size, shuffle=False)
test_loader = torch.utils.data.DataLoader(test_dataset, batch_size=batch_size, shuffle=False)

databunch = DataBunch(train_dl=train_loader,valid_dl=valid_loader)

# basic cross-entrophy loss
def loss_function(pred, target):
  loss_val = nn.CrossEntropyLoss()(pred,target)
  return loss_val


# training loop
# basic train loop
# callbacks can be added accordingly to modify training e.g. gradient clipping, early stop, lr rate schedule

def train_model(learn, output_dim =12, lr=0.001, batch_size=64, n_epochs=12):


    ### Train
    for epoch in range(n_epochs):
        learn.fit(1) # takes model to cuda if available

        ### Validation accuracy
        learn.model.eval()
        valid_preds = np.zeros((len(X_valid)))
        valid_raw_preds = torch.zeros(len(X_valid), output_dim)

        for i, x_batch in enumerate(valid_loader):


          X = x_batch[0].cuda()
          y_pred = nn.Softmax(dim=-1)(learn.model(X).detach())
          valid_preds[i * batch_size:(i + 1) * batch_size] =  y_pred.argmax(dim=-1).cpu().numpy()
          valid_raw_preds[i * batch_size:(i + 1) * batch_size] = y_pred

        print("Vaidation accuracy: {:.2f}%".format((valid_preds == y_valid).sum()/len(valid_preds)*100 ))

        ###########


    return valid_raw_preds



# hyperparameters for LSTM model
NUM_MODELS = 1 # ensembling of more models (slightly different architecture and seed) can be helpful
LSTM_UNITS = 128
DENSE_HIDDEN_UNITS = 4 * LSTM_UNITS
embed_size = 50
# Note: these parameters can be tunes for improving model performance


# targets
num_targets = 12


# init LSTM model
LUT = ModelEmbedding(max_features, embed_size, dropout = 0.3)
NET = NeuralNet(embed_size, LSTM_UNITS, DENSE_HIDDEN_UNITS, num_targets)
model = LSTM_model(LUT, NET)

# Fast ai learner
learn = Learner(databunch, model, loss_func=loss_function)



# train model
LSTM_valid_raw_preds = train_model(learn,output_dim=num_targets, lr = 1.0e-3)


# test set prediction

LSTM_pred_raw = torch.zeros(len(X_test), num_targets)
test_preds = np.zeros((len(X_test)))
learn.model.eval()

for i, x_batch in enumerate(test_loader):
    X = x_batch[0].cuda()
    y_pred = nn.Softmax(dim=-1)(learn.model(X).detach())
    LSTM_pred_raw[i * batch_size:(i + 1) * batch_size] = y_pred
    test_preds[i * batch_size:(i + 1) * batch_size] =  y_pred.argmax(dim=-1).cpu().numpy()
###

# save LSTM prediction
np.savetxt("LSTM_ytest.txt",test_preds.astype(int), fmt='%d')


# CNN model class
class CNN_Text(nn.Module):

    def __init__(self, max_features=28, e_char = 50,  kernel_sizes = [3,4,5,6, 10], num_filters =64, dropout_rate = 0.2, num_targets = 12):

        super(CNN_Text, self).__init__()

        # max_features: number of alphabets and <s>, </s>
        # e_char: char dimension
        # kernel_sizes: a list of kernel_sizes to consider
        # num_filters: number of filters to consider for each kernel_size
        # num_targets: number of authors


        self.e_char = e_char
        self.max_features = max_features
        self.kernel_sizes = kernel_sizes
        self.num_filters = num_filters
        self.num_targets = num_targets
        self.dropout_rate = dropout_rate

        in_channels = 1
        out_channles = self.num_filters

        num_latent = out_channles*len(kernel_sizes)


        # layers
        self.embed = nn.Embedding(max_features, e_char)
        self.conv_cnn = nn.ModuleList([nn.Conv2d(in_channels, out_channles, (K, e_char)) for K in kernel_sizes])
        self.dropout = nn.Dropout(dropout_rate)

        self.out = nn.Linear(num_latent, num_targets)


    def forward(self, x):

        x = self.embed(x)  # (batch, max_seq, e_char)

        x = x.unsqueeze(1)  # (batch, in_channels, max_seq, e_char)

        x = [F.relu(conv(x)).squeeze(dim =-1) for conv in self.conv_cnn]
        # list of tensors with shape (batch, out_channels, max_seq)  # conv(x) --> (batch, out_channels, max_seq, 1)

        x = [F.max_pool1d(i, i.size(2)).squeeze(dim=-1) for i in x]
        # list of tensors with shape (batch, out_channels) # max pool across char sequence max([:max_seq])

        x = torch.cat(x, 1) # (batch, out_channels*num_kernesl)


        x = self.dropout(x)  # (batch, out_channels*num_kernesl)
        results = self.out(x)

        return results


### CNN model init
model = CNN_Text()
learn = Learner(databunch, model, loss_func=loss_function)


# train cnn model
num_targets=12
CNN_valid_raw_preds = train_model(learn,lr=1.0e-3, output_dim=num_targets)

# CNN test set prediction

# test set prediction
CNN_pred_raw = torch.zeros(len(X_test), num_targets)
test_preds = np.zeros((len(X_test)))

learn.model.eval()

for i, x_batch in enumerate(test_loader):
    X = x_batch[0].cuda()
    y_pred = nn.Softmax(dim=-1)(learn.model(X).detach())
    CNN_pred_raw[i * batch_size:(i + 1) * batch_size] = y_pred
    test_preds[i * batch_size:(i + 1) * batch_size] =  y_pred.argmax(dim=-1).cpu().numpy()
###
# save CNN prediction
np.savetxt("CNN_ytest.txt",test_preds.astype(int), fmt='%d')

class ModelAttn(nn.Module):
    def __init__(self, LUT, NeuralNetAttn):

        super(ModelAttn, self).__init__()
        self.LUT = LUT
        self.Net = NeuralNetAttn

    def forward(self, x, lengths=None):

        h_embedding = self.LUT(x.long())
        out = self.Net(h_embedding)

        return out


# hyperparameters
embed_size =50
hidden_size =128
num_targets = 12


LUT = ModelEmbedding(max_features, embed_size, dropout = 0.3)
NET = NeuralNetAttn(embed_size, hidden_size, num_targets)
model = ModelAttn(LUT, NET)

learn = Learner(databunch, model, loss_func=loss_function)

# training
Attn_valid_raw_preds = train_model(learn,lr=0.005, output_dim=num_targets)


# Attention model test set prediction

# test set prediction
Attn_pred_raw = torch.zeros(len(X_test), num_targets)
test_preds = np.zeros((len(X_test)))

learn.model.eval()

for i, x_batch in enumerate(test_loader):
    X = x_batch[0].cuda()
    y_pred = nn.Softmax(dim=-1)(learn.model(X).detach())
    Attn_pred_raw[i * batch_size:(i + 1) * batch_size] = y_pred
    test_preds[i * batch_size:(i + 1) * batch_size] =  y_pred.argmax(dim=-1).cpu().numpy()
###
# save Attn prediction
np.savetxt("Attn_ytest.txt",test_preds.astype(int), fmt='%d')

# simple averaging of three models (better ensemble can be performed with xgboost/lightgbm)

final_valid_raw_preds = 0.3*LSTM_valid_raw_preds + 0.4*CNN_valid_raw_preds + 0.3*Attn_valid_raw_preds
valid_preds = final_valid_raw_preds.argmax(dim=-1).cpu().numpy()
print("Expected accuracy: {:.2f}%".format((valid_preds == y_valid).sum()/len(valid_preds)*100 ))

final_test_raw_preds = 0.3*LSTM_pred_raw + 0.4*CNN_pred_raw + 0.3*Attn_pred_raw
test_preds = final_test_raw_preds.argmax(dim=-1).cpu().numpy()
# save test preds
np.savetxt("ytest.txt",test_preds.astype(int), fmt='%d')