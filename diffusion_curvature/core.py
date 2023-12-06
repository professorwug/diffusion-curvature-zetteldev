# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/1 Core.ipynb.

# %% auto 0
__all__ = ['DiffusionCurvature', 'fill_diagonal']

# %% ../nbs/1 Core.ipynb 8
import pygsp
import jax
import jax.numpy as jnp
from fastcore.all import *
import skdim
import scipy
from inspect import getfullargspec
from typing import Callable, Literal, get_args, get_origin
import graphtools
from tqdm.auto import trange, tqdm

from jax.experimental import sparse


from .graphs import diff_aff, diff_op, diffusion_matrix_from_affinities
from .heat_diffusion import heat_diffusion_on_signal, kronecker_delta, jax_power_matrix
from .diffusion_laziness import wasserstein_spread_of_diffusion, entropy_of_diffusion
from .distances import phate_distances_differentiable
from .comparison_space import EuclideanComparisonSpace, fit_comparison_space_model, euclidean_comparison_graph, construct_ndgrid_from_shape, diffusion_coordinates, load_average_entropies
from .clustering import enhanced_spectral_clustering
# from .normalizing_flows import neural_flattener
from .vne import optimal_t_via_vne
from .utils import random_jnparray
import diffusion_curvature

import torch

# import deepdish
import h5py

_DIFFUSION_TYPES = Literal['diffusion matrix','heat kernel']
_LAZINESS_METHOD = Literal['Wasserstein','Entropic']
_FLATTENING_METHOD = Literal['Neural', 'Fixed', 'Mean Fixed']
_COMPARISON_METHOD = Literal['Ollivier', 'Subtraction']


class DiffusionCurvature():
    def __init__(
            self,
            diffusion_type:_DIFFUSION_TYPES = 'diffusion matrix', # Either ['diffusion matrix','heat kernel']
            laziness_method: _LAZINESS_METHOD = 'Wasserstein', # Either ['Wasserstein','Entropic']
            flattening_method: _FLATTENING_METHOD = 'Fixed', # Either ['Neural', 'Fixed', 'Mean Fixed']
            comparison_method: _COMPARISON_METHOD = 'Ollivier', # Either ['Ollivier', 'Subtraction']
            dimest = None, # Dimension estimator to use. If none, defaults to kNN.
            points_per_cluster = None, # Number of points to use in each cluster when constructing comparison spaces. Each comparison space takes about 20sec to construct, and has different sampling and dimension. If 1, constructs a different comparison space for each point; if None, constructs just one comparison space.
            comparison_space_size_factor = 1, # Number of points in comparison space is the number of points in the original space divided by this factor.
            use_grid=False, # If True, uses a grid of points as the comparison space. If False, uses a random sample of points.            
            max_flattening_epochs=50,     
            comparison_space_file = "../data/entropies_averaged.h5"   
    ):
        store_attr()
        self.D = None
        if self.dimest is None:
            self.dimest = skdim.id.KNN()
        if self.flattening_method == "Mean Fixed":
            self.SGT = load_average_entropies(comparison_space_file)
            # deepdish.io.load("../data/sgt_peppers_averaged_flat_entropies.h5") # dict of dim x knn x ts containing precomputed flat entropies.

    def unsigned_curvature(
            self,
            G:pygsp.graphs.Graph, # PyGSP input Graph
            t:int, # Scale at which to compute curvature; number of steps of diffusion.
            idx=None, # the index at which to compute curvature. If None, computes for all points. TODO: Implement
            # The below are used internally
            _also_return_first_scale = False, # if True, calculates the laziness measure at both specified t and t=1. The distances (if used) are calcualted with the larger t.
            D = None, # Supply manifold distances yourself to override their computation. Only used with the Wasserstein laziness method.
    ):
        n = G.L.shape[0]
        # Compute diffusion matrix
        match self.diffusion_type:
            case 'diffusion matrix':
                # P = diffusion_matrix_from_affinities(G.K)
                P = diff_op(G).todense() # is sparse, by default
                P = jnp.array(P)
                if t is None: t = optimal_t_via_vne(P)
                Pt = jax_power_matrix(P,t)
            case 'heat kernel':
                signal = jnp.eye(n) if idx is not None else kronecker_delta(n,idx=idx)
                Ps = heat_diffusion_on_signal(G, signal, [1,t])
                P = Ps[0]
                Pt = Ps[1]
            case _:
                raise ValueError(f"Diffusion Type {self.diffusion_type} not in {_DIFFUSION_TYPES}")
        match self.laziness_method:
            case "Wasserstein":
                if D is None: D = phate_distances_differentiable(Pt) #TODO: Could be more efficient here if there's an idx
                print(D[0])
                laziness = wasserstein_spread_of_diffusion(D,Pt) if idx is None else wasserstein_spread_of_diffusion(D[idx],Pt[idx])
                if _also_return_first_scale: laziness_nought = wasserstein_spread_of_diffusion(D,P)
            case "Entropic":
                laziness = entropy_of_diffusion(Pt) if idx is None else entropy_of_diffusion(Pt[idx])
                if _also_return_first_scale: laziness_nought = entropy_of_diffusion(P)
            case _:
                raise ValueError(f"Laziness Method {self.laziness_method} not in {_LAZINESS_METHOD}")
        if _also_return_first_scale: 
            return laziness, laziness_nought, P, Pt, t
        else:
            return laziness
    def curvature(
            self,
            G:pygsp.graphs.Graph, # Input Graph
            t:int, # Scale; if none, finds the knee-point of the spectral entropy curve of the diffusion operator
            idx=None, # the index at which to compute curvature. If None, computes for all points.
            dim = None, # the INTRINSIC dimension of your manifold, as an int for global dimension or list of pointwise dimensions; if none, tries to estimate pointwise.
            knn = 15, # Number of neighbors used in construction of graph;
    ):
        fixed_comparison_cache = {} # if using a fixed comparison space, saves by dimension
        def get_flat_spreads(dimension, jump_of_diffusion, num_points_in_comparison, cluster_idxs, verbose=False):
            match self.flattening_method:
                case "Fixed":
                    if dimension not in fixed_comparison_cache.keys():
                        if self.use_grid:
                            Rn = construct_ndgrid_from_shape(dimension, int(num_points_in_comparison**(1/dimension)))
                        else:
                            Rn = jnp.concatenate([jnp.zeros((1,dim)), 2*random_jnparray(num_points_in_comparison-1, dim)-1])
                        # construct a lattice in dim dimensions of num_points_in_comparison points
                        G = graphtools.Graph(Rn, anisotropy=1, knn=knn, decay=None,).to_pygsp()
                        if self.laziness_method == "Wasserstein": 
                            fixed_comparison_cache[dimension] = (G, scipy.spatial.distance_matrix(Rn,Rn))
                        else: 
                            fixed_comparison_cache[dimension] = (G, None)
                    G_euclidean, D_euclidean = fixed_comparison_cache[dimension]
                    fs = self.unsigned_curvature(G_euclidean,t,idx=0,D=D_euclidean)                    
                    return fs
                case "Kernel Matching":
                    model = EuclideanComparisonSpace(dimension=dimension, num_points=num_points_in_comparison, jump_of_diffusion=jump_of_diffusion,)
                    params = fit_comparison_space_model(model, max_epochs=1000)
                    if verbose: print(params)
                    euclidean_stuffs = model.apply(params) # dictionary containing A, P, D
                    W = fill_diagonal(euclidean_stuffs['A'],0)
                    G_euclidean = pygsp.graphs.Graph(
                        W = W,
                        lap_type = G.lap_type, # type of laplacian; we'll use the same as inputted.
                        )
                    fs = self.unsigned_curvature(G_euclidean,t,idx=0, D=euclidean_stuffs['D'])
                    return fs
                case "Neural":
                    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
                    NF = neural_flattener(device=device, max_epochs=self.max_flattening_epochs)
                    # for now, we assume that the neural flattener is only used with single point clusters
                    # TODO: generalize to multiple point clusters by finding centroid
                    distances_to_manfred = jnp.sum(jnp.array(
                        [jnp.linalg.norm(self.diff_coords - self.diff_coords[clustidx],axis=1) for clustidx in cluster_idxs]
                    ),axis=1)
                    idx_closest_to_manfred = jnp.argsort(distances_to_manfred)[:num_points_in_comparison]
                    diff_coords_of_comparison_space = self.diff_coords[idx_closest_to_manfred]
                    flattened_diff_coords = NF.fit_transform(
                        torch.tensor(diff_coords_of_comparison_space.tolist())
                    )
                    # construct graph out of these flattened coordinates
                    G_euclidean = graphtools.Graph(flattened_diff_coords, knn=15, decay=None, anisotropy=1).to_pygsp()
                    fs = self.unsigned_curvature(G_euclidean, t, idx=0)
                    return fs
                    # return G_euclidean, None # TODO: compute diffusion distances
                case "Mean Fixed":
                    dimension_checks_out = dimension in self.SGT.keys()
                    knn_checks_out = knn in self.SGT[dimension].keys() if dimension_checks_out else False
                    t_checks_out = t in self.SGT[dimension][knn].keys() if knn_checks_out else False
                    if not (dimension_checks_out and knn_checks_out and t_checks_out):
                        # compute the old way
                        print("Flat space not precomputed; computing now")
                        self.flattening_method = "Fixed"
                        return get_flat_spreads(
                            dimension = dimension,
                            jump_of_diffusion = jump_of_diffusion,
                            num_points_in_comparison = num_points_in_comparison,
                            cluster_idxs = cluster_idxs,
                            verbose=verbose
                            )
                    else:
                        return self.SGT[dimension][knn][t]
                        

        # Start by estimating the manifold's unsigned curvature, i.e. spreads of diffusion
        manifold_spreads, manifold_spreads_nought, P, Pt, t = self.unsigned_curvature(G,t,idx, _also_return_first_scale=True)

        n = G.L.shape[0]
        if dim is None: # The dimension wasn't supplied; we'll estimate it pointwise
            print("estimating local dimension of each point... may take a while")
            ldims = self.dimest.fit_pw(
                                G.data, #TODO: Currently this requires underlying points!
                                n_neighbors = 100,
                                n_jobs = 1)
            dims_per_point = np.round(ldims.dimension_pw_).astype(int)
        else: # the dimension *was* supplied, but it may be either a single global dimension or a local dimension for each point
            if isinstance(dim, int):
                dims_per_point = jnp.ones(G.P.shape[0], dtype=int)*dim
            else:
                dims_per_point = dim

        if self.flattening_method == "Neural":
            # we need to compute coordinates to flatten. We'll use diffusion maps for this.
            self.diff_coords = diffusion_coordinates(G, t=t)[:,:dim]
        
        flat_spreads = jnp.zeros(n)
        num_points_in_comparison = n // self.comparison_space_size_factor # TODO: Can surely find a better heuristic here
        num_clusters = n // self.points_per_cluster if self.points_per_cluster is not None else 1
        if num_clusters == n: cluster_labels = jnp.arange(n)
        elif idx is not None: 
            cluster_labels = jnp.ones(n) # if a single index is supplied, there's only one cluster.
            cluster_labels = cluster_labels.at[idx].set(0)
            num_clusters = 1
        else: 
            cluster_labels = enhanced_spectral_clustering(G, manifold_spreads, dim=dim, num_clusters=num_clusters, )

        for i in range(num_clusters):
            cluster_idxs = jnp.where(cluster_labels==i)[0]
            average_dim_in_cluster = int(jnp.round(jnp.mean(dims_per_point[cluster_idxs])))
            average_spread_in_cluster = jnp.mean(manifold_spreads_nought[cluster_idxs])
            fs = get_flat_spreads(
                dimension = average_dim_in_cluster,
                jump_of_diffusion = average_spread_in_cluster,
                num_points_in_comparison = num_points_in_comparison,
                cluster_idxs = cluster_idxs,
                verbose=True
                )
            # fs = self.unsigned_curvature(G_euclidean,t,idx=0)
            flat_spreads = flat_spreads.at[cluster_idxs].set(
                    fs
                )
        match self.comparison_method:
            case "Ollivier":
                ks = 1 - manifold_spreads/flat_spreads
            case "Subtraction":
                ks = flat_spreads - manifold_spreads
            case _:
                raise ValueError(f'Comparison method must be in {_COMPARISON_METHOD}')    
        if idx is not None: ks = ks[idx]
        return ks #, flat_spreads, manifold_spreads, P, Pt
    
def fill_diagonal(a, val):
  assert a.ndim >= 2
  i, j = jnp.diag_indices(min(a.shape[-2:]))
  return a.at[..., i, j].set(val)
