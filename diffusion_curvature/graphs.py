# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/Graphs.ipynb.

# %% auto 0
__all__ = ['diff_op', 'kernel_degree', 'diff_aff', 'get_knn_graph', 'get_alpha_decay_graph', 'get_scanpy_graph', 'get_umap_graph',
           'generic_kernel', 'diffusion_matrix_from_affinities']

# %% ../nbs/Graphs.ipynb 2
import graphtools as gt
import pygsp
from typing import Union
from graphtools.matrix import set_diagonal, to_array
from scipy import sparse
from sklearn.preprocessing import normalize
import numpy as np

try:
    # optional dependencies
    import scanpy as sc
    import umap
except ImportError as imp_err:
    sc = imp_err
    umap = imp_err

# %% ../nbs/Graphs.ipynb 3
def diff_op(graph):
    """
    Compute the diffusion operator for a pygsp graph.
    """
    assert isinstance(graph, pygsp.graphs.Graph)
    # K = set_diagonal(graph.W, 1)
    diff_op_ = normalize(graph.W, norm="l1", axis=1)
    return diff_op_


def kernel_degree(graph):
    """
    Compute the kernel degree for a pygsp graph.
    """
    assert isinstance(graph, pygsp.graphs.Graph)
    K = set_diagonal(graph.W, 1)
    return to_array(K.sum(axis=1)).reshape(-1, 1)


def diff_aff(graph):
    """
    Compute the diffusion affinity for a pygsp graph.
    """
    assert isinstance(graph, pygsp.graphs.Graph)
    K = set_diagonal(graph.W, 1)
    row_degrees = kernel_degree(graph)

    if sparse.issparse(K):
        # diagonal matrix
        degrees = sparse.csr_matrix(
            (
                1 / np.sqrt(row_degrees.flatten()),
                np.arange(len(row_degrees)),
                np.arange(len(row_degrees) + 1),
            )
        )
        return degrees @ K @ degrees
    else:
        col_degrees = row_degrees.T
        return (K / np.sqrt(row_degrees)) / np.sqrt(col_degrees)


###------------------------Graphs Classes ----------------------------###


def get_knn_graph(X, knn=5, **kwargs):
    return pygsp.graphs.NNGraph(X, k=knn)


def get_alpha_decay_graph(
    X,
    knn: int = 5,
    decay: float = 40.0,
    anisotropy: float = 0,
    n_pca: int = None,
    **kwargs
):
    return gt.Graph(
        X,
        knn=knn,
        decay=decay,
        anisotropy=anisotropy,
        n_pca=n_pca,
        use_pygsp=True,
        random_state=42,
    ).to_pygsp()


def get_scanpy_graph(X, knn=5, **kwargs):

    if isinstance(sc, ImportError):
        raise ImportError("Scanpy is not installed.")

    adata = sc.AnnData(X)
    sc.pp.neighbors(adata, n_neighbors=knn)
    w = adata.obsp["connectivities"]
    return pygsp.graphs.Graph(w)


def get_umap_graph(X, knn=5, **kwargs):  # knn default to 15 in UMAP
    if isinstance(umap, ImportError):
        raise ImportError("UMAP is not installed.")
    umap_op = umap.UMAP(n_neighbors=knn, metric="euclidean")
    umap_op.fit(X)
    w = umap_op.graph_.toarray()
    return pygsp.graphs.Graph(w)

# %% ../nbs/Graphs.ipynb 5
import jax
import jax.numpy as jnp

def generic_kernel(
        D, # distance matrix
        sigma, # kernel bandwidth
        anisotropic_density_normalization, 

):  
    W = (1/(sigma*np.sqrt(2*jnp.pi)))*jnp.exp((-D**2)/(2*sigma**2))
    D = jnp.diag(1/((jnp.sum(W,axis=1)+1e-8)**anisotropic_density_normalization))
    W = D @ W @ D
    return W

# %% ../nbs/Graphs.ipynb 6
def diffusion_matrix_from_affinities(
        W
):
    W = W + jnp.eye(len(W))*1e-8
    D = jnp.diag(1/jnp.sum(W,axis=1))
    P = D @ W
    return P
