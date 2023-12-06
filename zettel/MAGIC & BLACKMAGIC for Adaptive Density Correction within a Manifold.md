Within the manifold, we want points to repel each other. Outside of the manifold, we want them to attract. 

So what if, using a kernel density estimation, we switch between MAGIC (attraction via $P^tX$ for points outside the manifold) and [[BLACKMAGIC]] (repulsion, the inverse $P^{-t}X$ of the diffusion matrix, for points within the manifold).

We could formulate this as scaling by a density $\alpha \in [0,1]$:

$$
 x_{n} = P^{t*{\sigma(\alpha)}} x_{n-1}
$$
This would be done for some number of steps, individually for each point (rather than powering the diffusion matrix).