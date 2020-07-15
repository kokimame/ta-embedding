import os
import json
import numpy as np
import spacy
import torch
from tqdm import tqdm
from itertools import permutations

class MarginAdapter:
    def __init__(self, label_list, base_margin, description_file=None):
        self.base_margin = base_margin

        self.initialize_lookup(label_list, description_file)

        self.pairwise_dists = {}
        for l1, l2 in permutations(self.label_to_vector.keys(), 2):
            dist = np.linalg.norm(
                self.label_to_vector[l1] - self.label_to_vector[l2]
            )
            assert (l1, l2) not in self.pairwise_dists
            self.pairwise_dists[(l1, l2)] = dist
        self.average_dist = np.mean(list(self.pairwise_dists.values()))

        # Similar to pairwise distance
        # Either of them will be discarded
        self.dist_semantic = {}
        for l1, l2 in permutations(self.label_to_vector.keys(), 2):
            dist = np.linalg.norm(
                self.label_to_vector[l1] - self.label_to_vector[l2]
            )
            assert (l1, l2) not in self.dist_semantic
            self.dist_semantic[(l1, l2)] = dist / 4 - self.base_margin


    def initialize_lookup(self, label_list, description_file):
        nlp = spacy.load('en_core_web_md')
        description_lookup = {}
        if description_file:
            assert description_file.endswith('.json')
            assert os.path.exists(description_file)
            with open(description_file, 'r') as f:
                description_lookup = json.load(f)

        self.label_to_vector = {}
        # Flatten list of list to list
        label_sequence = [label for sublist in label_list for label in sublist]
        for label in tqdm(label_sequence, desc='Computing word2vec for labels'):
            if label in description_lookup:
                description = description_lookup[label]
            else:
                description = label
            if label not in self.label_to_vector:
                vectors = np.asarray([word.vector for word in nlp(description)])
                mean_vector = np.mean(vectors, axis=0)
                self.label_to_vector[label] = mean_vector


    def adapt(self, labels, sel_pos, sel_neg):
        margin_list = []
        for pos, neg in zip(sel_pos, sel_neg):
            pos_label = labels[pos]
            neg_label = labels[neg]
            dist = self.pairwise_dists[(pos_label, neg_label)]

            if dist > self.average_dist:
                margin_list.append([self.base_margin + 1])
            else:
                margin_list.append([self.base_margin - 1])

        adapted_margin = torch.tensor(margin_list)
        return adapted_margin

    def adapt2(self, labels, sel_pos, sel_neg):
        margin_list = []
        for i_pos, i_neg in zip(sel_pos, sel_neg):
            pos_label = labels[i_pos]
            neg_label = labels[i_neg]
            dist = self.dist_semantic[(pos_label, neg_label)]
            margin_list.append([self.base_margin + dist])


        adapted_margin = torch.tensor(margin_list)
        return adapted_margin