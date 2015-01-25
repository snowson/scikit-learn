"""
THis module implement no binary tree classifier
"""
from __future__ import division

import numbers
import numpy as np
from abc import ABCMeta, abstractmethod
from warnings import warn

from six import string_types

from ..base import BaseEstimator, ClassifierMixin
from ..externals import six
from ..externals.six.moves import xrange
from ..feature_selection.from_model import _LearntSelectorMixin
from ..utils import array2d
from ..utils.validation import check_arrays

from ._nbtree import DataObject
# from ._nbtree import FeatureParser
from ._nbtree import Criterion
from ._nbtree import Splitter
from ._nbtree import LapSplitter
from ._nbtree import ExpSplitter
from ._nbtree import NBTreeBuilder
from ._nbtree import Tree
from . import _nbtree

# __all__ = ["NBTreeClassifier"]

# =================================================================
# Types and constants
# =================================================================

DTYPE  = _nbtree.DTYPE  
DOUBLE = _nbtree.DOUBLE

NO_DIFF_PRIVACY_MECH  = 0
LAP_DIFF_PRIVACY_MECH = 1
EXP_DIFF_PRIVACY_MECH = 2

CRITERIA_CLF ={ "gini"      : _nbtree.Gini, 
                "entropy"   : _nbtree.Entropy, 
                "lapentropy": _nbtree.LapEntropy } 

SPLITTERS = { NO_DIFF_PRIVACY_MECH  : ExpSplitter, 
              LAP_DIFF_PRIVACY_MECH : LapSplitter,
              EXP_DIFF_PRIVACY_MECH : ExpSplitter }

# =================================================================
# Tree
# =================================================================
class NBTreeClassifier(six.with_metaclass(ABCMeta, BaseEstimator, 
                                        ClassifierMixin, _LearntSelectorMixin)):

    def __init__(self,
                
                diffprivacy_mech = NO_DIFF_PRIVACY_MECH ,
                budget = -1.0,
                
                criterion = "gini",

                max_depth = 5,
                max_features = 14,
                min_samples_leaf = 0,

                is_prune = True,
                CF = 0.25,

                random_state = 1,
                print_tree = True ,
                debug = False,

                meta = None
                ):

        self.diffprivacy_mech = diffprivacy_mech
        self.budget = budget
        self.criterion = criterion
       

        self.max_depth = max_depth
        self.max_features = max_features 
        self.min_samples_leaf = min_samples_leaf

        self.is_prune = is_prune
        self.CF = CF
    
        self.random_state = random_state
        self.print_tree = print_tree
        self.debug = debug

        self.meta  = meta

        # inner structure
        self.tree_ = None

    def set_meta(self, meta):
        self.meta = meta

    def fit(self,
            X, y,
            sample_weight = None,
            check_input   = None    # for randomforest, no use
            ):

        # set diffprivacy mech
        diffprivacy_mech = self.diffprivacy_mech
        if isinstance(diffprivacy_mech, string_types):
            if diffprivacy_mech in ["no", "n"]:
                diffprivacy_mech = NO_DIFF_PRIVACY_MECH
            elif diffprivacy_mech in ["laplace", "lap", "l"]:
                diffprivacy_mech = LAP_DIFF_PRIVACY_MECH
            elif diffprivacy_mech in ["exponential", "exp", "e"]:
                diffprivacy_mech = EXP_DIFF_PRIVACY_MECH
            else:
                raise ValueError("diffprivacy_mech %s is illegal"
                                    %diffprivacy_mech)

        elif isinstance(diffprivacy_mech, (numbers.Integral, np.integer)):
            if diffprivacy_mech not in [NO_DIFF_PRIVACY_MECH, 
                                        LAP_DIFF_PRIVACY_MECH, 
                                        EXP_DIFF_PRIVACY_MECH]:
                raise ValueError
        else:
            raise ValueError
        self.diffprivacy_mech_ = diffprivacy_mech

        # set budget
        budget = self.budget
        if diffprivacy_mech is NO_DIFF_PRIVACY_MECH:
            budget = -1.0
        self.budget_ = budget
      
        # set criterion
        criterion = self.criterion
        if diffprivacy_mech is LAP_DIFF_PRIVACY_MECH:
            criterion = "lapentropy"
        if criterion not in ["gini", "entropy", "lapentropy"]:
            raise Exception("Invalid criterion %s"%criterion)
        self.criterion_ = criterion
       
        # set random_state
        random_state = self.random_state
        if isinstance(random_state, (numbers.Integral, np.integer)):
            random_state = np.random.RandomState(random_state)
        elif isinstance(random_state, np.random.RandomState):
            random_state = random_state
        else:
            random_state = np.random.RandomState()
        self.random_state_ = random_state

        max_depth = self.max_depth
        if max_depth <= 0:
            raise ValueError("max_depth must be greater than zero.")

        max_features = self.max_features 
        min_samples_leaf = self.min_samples_leaf

        is_prune = self.is_prune
        CF = self.CF

        print_tree = self.print_tree
        debug = self.debug

        # check meta
        if self.meta is None:
            raise Exception("Attribute meta is None, \
                        please set it first by set_meta()")
        meta = self.meta

        X, = check_arrays(X, dtype=DTYPE, sparse_format="dense")
        if y.ndim == 1:
            # reshape is necessary to preserve the data contiguity against vs
            # [:, np.newaxis] that does not.
            y = np.reshape(y, (-1, 1))

        if getattr(y, "dtype", None) != DOUBLE or not y.flags.contiguous:
            y = np.ascontiguousarray(y, dtype=DOUBLE)
 
        # check sample_weight
        n_samples , n_features = X.shape
        if sample_weight is not None:

            if (getattr(sample_weight, "dtype", None) != DOUBLE or
                        not sample_weight.flags.contiguous):
                sample_weight = np.ascontiguousarray(
                    sample_weight, dtype=DOUBLE)
            if len(sample_weight.shape) > 1:
                raise ValueError("Sample weights array has more "
                                 "than one dimension: %d" %
                                 len(sample_weight.shape))
            if len(sample_weight) != n_samples:
                raise ValueError("Number of weights=%d does not match "
                                 "number of samples=%d" %
                                 (len(sample_weight), n_samples))


        # init Data
        dataobject = DataObject(X, y, meta, sample_weight)
        criterion =CRITERIA_CLF[self.criterion](dataobject, random_state, debug)
        splitter  =SPLITTERS[diffprivacy_mech ](criterion,  random_state, debug)

        tree = Tree(dataobject, debug)
        self.tree_ = tree

        builder = NBTreeBuilder(diffprivacy_mech,
                              budget,
                              splitter,
                              max_depth,
                              max_features,
                              min_samples_leaf,
                              random_state,
                              print_tree,
                              is_prune,
                              CF)
        # 4. build tree
        builder.build( tree, dataobject, debug)
        
        self.data_ = dataobject 
        if self.data_.n_outputs == 1:
            self.data_.n_classes = self.data_.n_classes[0]
            self.data_.classes = self.data_.classes[0]
        return self

    @property
    def n_outputs_(self):
        return self.data_.n_outputs

    @property 
    def n_classes_(self):
        return self.data_.n_classes

    @property 
    def classes_(self):
        return self.data_.classes

    def predict(self, X):
        """Predict class or regression value for X.

        For a classification model, the predicted class for each sample in X is
        returned.

        Parameters
        ----------
        X : array-like of shape = [n_samples, n_features]
            The input samples.

        Returns
        -------
        y : array of shape = [n_samples] or [n_samples, n_outputs]
            The predicted classes, or the predict values.
        """
        debug = self.debug
        if debug:
            print "get into predict"
        
        if getattr(X, "dtype", None) != DTYPE or X.ndim != 2:
            X = array2d(X, dtype=DTYPE)


        n_samples, n_features = X.shape

        if self.tree_ is None:
            raise Exception("Tree not initialized. Perform a fit first")

        if self.data_.n_features != n_features:
            raise ValueError("Number of features of the model must "
                             " match the input. Model n_features is %s and "
                             " input n_features is %s "
                             % (self.data_.n_features, n_features))

        proba = self.tree_.predict(X)

        if debug:
            print "get out of tree.predict"

        # Classification
        if isinstance(self, ClassifierMixin):
            if self.data_.n_outputs == 1:
                return self.data_.classes.take(np.argmax(proba, axis=1), axis=0)

            else:
                predictions = np.zeros((n_samples, self.data_.n_outputs))

                for k in xrange(self.data_.n_outputs):
                    predictions[:, k] = self.data_.classes[k].take(
                        np.argmax(proba[:, k], axis=1),
                        axis=0)

                return predictions

    def predict_proba(self, X):
        """Predict class probabilities of the input samples X.

        Parameters
        ----------
        X : array-like of shape = [n_samples, n_features]
            The input samples.

        Returns
        -------
        p : array of shape = [n_samples, n_classes], or a list of n_outputs
            such arrays if n_outputs > 1.
            The class probabilities of the input samples. The order of the
            classes corresponds to that in the attribute `classes_`.
        """
        if getattr(X, "dtype", None) != DTYPE or X.ndim != 2:
            X = array2d(X, dtype=DTYPE)

        n_samples, n_features = X.shape

        if self.tree_ is None:
            raise Exception("Tree not initialized. Perform a fit first.")

        if self.data_.n_features != n_features:
            raise ValueError("Number of features of the model must "
                             " match the input. Model n_features is %s and "
                             " input n_features is %s "
                             % (self.data_.n_features, n_features))

        proba = self.tree_.predict(X)

        if self.data_.n_outputs == 1:
            proba = proba[:, :self.data_.n_classes]
            normalizer = proba.sum(axis=1)[:, np.newaxis]
            normalizer[normalizer == 0.0] = 1.0
            proba /= normalizer

            return proba

        else:
            all_proba = []

            for k in xrange(self.data_.n_outputs_):
                proba_k = proba[:, k, :self.data_.n_classes_[k]]
                normalizer = proba_k.sum(axis=1)[:, np.newaxis]
                normalizer[normalizer == 0.0] = 1.0
                proba_k /= normalizer
                all_proba.append(proba_k)

            return all_proba

    @property
    def feature_importances_(self): 
    
        """Return the feature importances.

        The importance of a feature is computed as the (normalized) total
        reduction of the criterion brought by that feature.
        It is also known as the Gini importance.

        Returns
        -------
        feature_importances_ : array, shape = [n_features]
        """
        if self.tree_ is None:
            raise ValueError("Estimator not fitted, "
                             "call `fit` before `feature_importances_`.")

        return self.tree_.compute_feature_importances()


