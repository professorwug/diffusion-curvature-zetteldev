---
aliases: 
tags: 
---
In [[Demonstration of Holes in Manifold Graphs]], we saw that spurious positive curvature was caused by a sparse sampling. How can this be remedied?

The presumption is that [[Sampled data has three regimes - noisy, true to local geometry, and oversmoothed]], corresponding to high-frequency noise, band-frequency, and low-frequency signals in a graph fourier transform. We have some idea how to identify these - [[The elbow of spectral Diffusion Entropy identifies the scale of local geometry]]; this is how we set the $t$ in diffusion curvature. But, in the cases above, a


# Better Graph Construction

1. Constructing a graph from phate distances? (double diffusion, suggested by Edward, poo-poo’d by Smita.)
2. Coarsening of the graph?

# Some sort of pre-smoothing
1. ~~MAGIC?~~ ([[MAGIC applied to Holey Graphs]] disproves this and SUGAR; )
	1. As I recall, this applies the diffusion matrix to data directly to smooth it. It likely also incurs some deformation of curvature.
	2. It is known that MAGIC can pull outliers onto the data manifold. The question is what it does with *negative* outliers - points that should be on the manifold but aren’t. What happens to holes?
2. ~~SUGAR~~?
	1. This is true of the holes but not of true negative curvature: adding points in the middle disrupts them. If SUGAR can sprinkle extra points, sucked into the manifold – and, crucially, these points would tend to land in the midst of holes, this could solve our problem.
	2. The challenge would be whether SUGAR is any more likely to add points to the (in high dimensions, numerous) holes in the data, or if it’s actually less likely, as sprinkled points are likely attracted to existing points.

These holes are characterized by non-uniform density: higher around the edges, lower in the middle. We really just need points to diffuse from the areas of high to low density - while remaining on the manifold.

# Some sort of post-smoothing
