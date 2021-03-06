import os
import torch
from torch.utils.data import DataLoader

from dataset.dataset_full_size import DatasetFull
from models.model_move import MOVEModel
from models.model_vgg import VGGModel
from models.model_move_nt import MOVEModelNT
from utils.utils import average_precision
from utils.utils import pairwise_distance_matrix
from utils.utils import import_dataset_from_pt
from tqdm import tqdm

MYPREFIX = f'{os.environ["HOME"]}/Project/Master_Files'

def test(model, test_loader, norm_dist=1):
    """
    Obtaining pairwise distances of all elements in the test set. For using full length songs,
    we pass them to the model one by one
    :param model: model to be used for testing
    :param test_loader: dataloader for test
    :param norm_dist: whether to normalize distances by the embedding size
    :return: pairwise distance matrix of all elements in the test set
    """
    if torch.cuda.is_available():
        device = 'cuda:0'
    else:
        device = 'cpu'

    with torch.no_grad():  # deactivating gradient tracking for testing
        model.eval()  # setting the model to evaluation mode

        # tensor for storing all the embeddings obtained from the test set
        embed_all = torch.tensor([], device=device, dtype=torch.float)

        for batch_idx, item in enumerate(tqdm(test_loader, desc='Testing  the model .....')):

            if torch.cuda.is_available():  # sending the pcp features and the labels to cuda if available
                item = item.cuda()

            res_1 = model(item)  # obtaining the embeddings of each song in the mini-batch

            embed_all = torch.cat((embed_all, res_1))  # adding the embedding of the current song to the others

        dist_all = pairwise_distance_matrix(embed_all)  # calculating the condensed distance matrix

        if norm_dist:  # normalizing the distances
            dist_all /= model.fin_emb_size

    return dist_all


def evaluate(defaults, save_name, dataset_name):
    """
    Main evaluation function of MOVE. For a detailed explanation of parameters,
    please check 'python move_main.py -- help'
    :param save_name: name to save model and experiment summary
    :param emb_size: the size of the final embeddings produced by the model
    :param sum_method: the summarization method for the model
    :param final_activation: final activation to use for the model
    :param dataset: which dataset to evaluate the model on. (0) validation set, (1) da-tacos, (2) ytc
    :param dataset_name: name of the file to evaluate
    """
    emb_size, sum_method, final_activation, dataset, dataset_root = [
        defaults[key.strip()] for key in """
        emb_size, sum_method, final_activation, dataset, dataset_root
        """.split(',')
    ]
    print('Evaluating model {} on dataset {}.'.format(save_name, dataset_name))

    model_move = VGGModel(emb_size=256)

    # loading a pre-trained model
    model_name = 'saved_models/model_{}.pt'.format(save_name)

    model_move.load_state_dict(torch.load(model_name, map_location='cpu'))
    model_move.eval()

    # sending the model to gpu, if available
    if torch.cuda.is_available():
        model_move.cuda()

    # loading test data, initializing the dataset object and the data loader
    test_data, test_labels = import_dataset_from_pt(filename=dataset_name)

    test_map_set = DatasetFull(data=test_data, labels=test_labels)
    test_map_loader = DataLoader(test_map_set, batch_size=1, shuffle=False)

    # calculating the pairwise distances
    dist_map_matrix = test(model=model_move,
                           test_loader=test_map_loader).cpu()

    # calculating the performance metrics
    average_precision(
        os.path.join(dataset_root, f'{dataset_name}_val_ytrue.pt'),
        -1 * dist_map_matrix.clone() + torch.diag(torch.ones(len(test_data)) * float('-inf')),
    )
