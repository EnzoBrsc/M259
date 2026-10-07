"""Référence sérialisable, indépendante du point d'entrée de la commande."""

import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin


class FeatureReference(ClassifierMixin, BaseEstimator):
    """Classer par une seule statistique ; aucune information de la cible."""

    def fit(self, X, y):
        self.classes_ = np.array([0, 1])
        self.n_features_in_ = X.shape[1]
        return self

    def decision_function(self, X):
        return np.asarray(X)[:, 0]
