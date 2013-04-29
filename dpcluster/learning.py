import math
import numpy as np
import scipy.linalg
import scipy.special
import matplotlib.pyplot as plt

#TODO: gradient and hessian information not currently used except for grad log likelihood for the NIW distribution. Consider removing extra info.
class ExponentialFamilyDistribution:
    """ f(x|nu) = h(x) exp( nu*x - A(nu) )
        h is the base measure
        nu are the parameters
        x are the sufficient statistics
        A is the log partition function
    """
    #TODO: base measure assumed to be scalar. Needs to be fixed for generality.
    def log_base_measure(self,x, ret_ll_gr_hs = [True,False,False] ):
        pass
    def log_partition(self,nu, ret_ll_gr_hs = [True,False,False] ):
        pass

    #TODO: derivatives not implemented. Consider removing
    def ll(self,xs,nus,ret_ll_gr_hs = [True,False,False]  ):
        return ((np.einsum('ci,di->dc',nus,xs) 
            + self.log_base_measure(xs)[0]
            - self.log_partition(nus)[0][np.newaxis,:]  ),)
        
        
class Gaussian(ExponentialFamilyDistribution):
    """Multivariate Gaussian distribution
    """
    def __init__(self,d):
        self.dim = d
        self.lbm = math.log(2*np.pi)* (-d/2.0)
        self.inv = np.linalg.inv
        self.slogdet = np.linalg.slogdet

    def sufficient_stats(self,x):
        tmp = (x[:,np.newaxis,:]*x[:,:,np.newaxis]).reshape(x.shape[0],-1)
        return np.hstack((x,tmp))
    def sufficient_stats_dim(self):
        d = self.dim
        return d + d*d
    def log_base_measure(self,x,ret_ll_gr_hs = [True,True,True]):
        return (self.lbm, 0.0,0.0)
    def usual2nat(self,mus, Sgs):
        nu2 = np.array(map(self.inv,Sgs))
        nu1 = np.einsum('nij,nj->ni',nu2,mus)
        nu = np.hstack((nu1,-.5*nu2.reshape(nu2.shape[0],-1)))
        return nu
        
    def nat2usual(self,nus):
        d = self.dim
        nu1 = nus[:,:d]
        nu2 = nus[:,d:].reshape((-1,d,d))        
        Sgs = np.array(map(self.inv,-2.0*nu2))
        mus = np.einsum('nij,nj->ni',Sgs,nu1)
        return mus,Sgs
    def log_partition(self,nus):

        # todo: implement gradient and hessian
        d = self.dim 
        nu1 = nus[:,:d]
        nu2 = nus[:,d:].reshape((-1,d,d))        
        inv = np.array(map(self.inv,nu2))
        # TODO: einsum wrong:
        t1 = -.25* np.einsum('ti,tij,tj->t',nu1,inv,nu1)
        t2 = -.5*np.array(map(self.slogdet,-2*nu2))[:,1]
        return (t1+t2,)



class NIW(ExponentialFamilyDistribution):
    """ Normal Inverse Wishart distribution defined by
        f(mu,Sg|mu0,Psi,k) = N(mu|mu0,Sg/k) IW(Sg|Psi,k-p-2)
        where mu, mu0 \in R^p, Sg, Psi \in R^{p \cross p}, k > 2*p+1 \in R
        This is the exponential family conjugate prior for the Gaussian
    """
    def __init__(self,d):
        self.dim = d
        self.lbm = math.log(2*np.pi)* (-d/2.0)
    def sufficient_stats_dim(self):
        d = self.dim
        return d+d*d +2

    def log_base_measure(self,x,ret_ll_gr_hs = [True,True,True]):
        return (self.lbm, 0.0,0.0)
    def log_partition(self,nu, ret_ll_gr_hs= [True,False,False],
                no_k_grad=False ):
        
        # todo: implement hessian
        rt = ret_ll_gr_hs
        ll = None
        gr = None
        hs = None

        d = self.dim
        l1 = nu[:,:d]
        l2 = nu[:,d:-2].reshape(-1,d,d)
        l3 = nu[:,-2]
        l4 = nu[:,-1]
        
        nu = (l4-d-2).reshape(-1)
        psi = (l2 - 
            l1[:,:,np.newaxis]*l1[:,np.newaxis,:]/l3[:,np.newaxis,np.newaxis])

        if not no_k_grad:
            ld = np.array(map(np.linalg.slogdet,psi))[:,1]

        if rt[0]:
            if not nu.size==1:
                lmg = scipy.special.multigammaln(.5*nu,d)
            else:
                lmg = scipy.special.multigammaln(.5*nu[0],d)

            al = -.5*d*np.log(l3) + .5*nu*(d * np.log(2) - ld ) + lmg
            ll = al

        if rt[1]:
            inv = np.array(map(np.linalg.inv,psi))
            g1 = (nu/l3)[:,np.newaxis]* np.einsum('nij,nj->ni',inv,l1)
            g2 = -.5*nu[:,np.newaxis] *inv.reshape(l2.shape[0],-1)

            g3 = ( -.5 * d/l3
                - .5/l3 * (g1*l1).sum(1)  )[:,np.newaxis]

            if not no_k_grad:
                g4 = ( + .5 *d*np.log(2) - .5*ld + .5*self.multipsi(.5*nu,d)
                     )[:,np.newaxis]
            else:
                g4 = np.zeros((nu.shape[0],1))
                

            gr = np.hstack((g1,g2,g3,g4))

        if rt[2]:   
            # not implemented
            pass

        return (ll,gr,hs)

    def multipsi(self,a,d):
        res = np.zeros(a.shape)
        for i in range(d):
            res += scipy.special.psi(a - .5*i)
        return res    


    def sufficient_stats(self,mus,Sgs):

        Sgi = np.array(map(np.linalg.inv,Sgs))
        nu1 = np.einsum('nij,nj->ni',Sgi,mus)
        nu = np.hstack((nu1,-.5*Sgi.reshape(Sgi.shape[0],-1)))

        t1 = -.5* np.einsum('ti,tij,tj->t',mus,Sgi,mus)
        t2 = -.5*np.array(map(np.linalg.slogdet,Sgs))[:,1]
        return np.hstack((nu, t1[:,np.newaxis],t2[:,np.newaxis]))

    def usual2nat(self,mu0,Psi,k,nu):
        l3 = k.reshape(-1,1)
        l4 = (nu+2+self.dim).reshape(-1,1)
        l1 = mu0*l3
        l2 = Psi + l1[:,:,np.newaxis]*l1[:,np.newaxis,:]/k[:,np.newaxis,np.newaxis]

        return np.hstack((l1,l2.reshape(l2.shape[0],-1),l3,l4 ))

    def nat2usual(self,nu):

        d = self.dim
        l1 = nu[:,:d]
        l2 = nu[:,d:-2].reshape(-1,d,d)
        l3 = nu[:,-2]
        l4 = nu[:,-1]

        k = l3
        nu = l4 - 2 - d
        mu0 = l1/l3[:,np.newaxis]
        
        Psi = -l1[:,:,np.newaxis]*l1[:,np.newaxis,:]/l3[:,np.newaxis,np.newaxis]
        Psi += l2

        return mu0, Psi,k,nu

class ConjugatePair:
    def __init__(self,evidence_distr,prior_distr, prior_param):
        self.evidence = evidence_distr
        self.prior = prior_distr
        self.prior_param = prior_param
    def sufficient_stats(self,data):
        pass
    def posterior_ll(self,x,nu, ret_ll_gr_hs=[True,False,False],
            usual_x=False):
        
        if usual_x:
            x = self.sufficient_stats(x)
        ll,gr,hs = (None,None,None)

        n = x.shape[0]
        k,d = nu.shape

        nu_p = (nu[np.newaxis,:,:] + x[:,np.newaxis,:])
        
        llk, grk, hsk =  self.prior.log_partition(nu_p.reshape((-1,d)),
                        ret_ll_gr_hs)
        

        if ret_ll_gr_hs[0]:
            t1 = self.evidence.log_base_measure(x)[0]
            t2 = self.prior.log_partition(nu)[0]
            t3 = llk.reshape((n,k))
            
            ll = t1 - t2[np.newaxis,:] + t3 

        if ret_ll_gr_hs[1]:

            gr = grk.reshape((n,k,d))
            gr += self.evidence.log_base_measure(x)[1]

        if ret_ll_gr_hs[2]:
            hs = hsk.reshape((n,k,d,d))
            hs += self.evidence.log_base_measure(x)[2]
        
        return (ll,gr,hs)


    def sufficient_stats_dim(self):
        return self.prior.sufficient_stats_dim()

class GaussianNIW(ConjugatePair):
    #TODO: this is just a multivariate-T. Should have a separate class for it
    def __init__(self,d):
        # old version used 2*d+1+2, this seems to work well
        # 2*d + 1 was also a good choice but can't remember why
        ConjugatePair.__init__(self,
            Gaussian(d),
            NIW(d),
            np.concatenate([np.zeros(d*d + d), np.array([0, 2*d+1])])
            )
    def sufficient_stats(self,data):
        x = self.evidence.sufficient_stats(data)
        x1 = np.insert(x,x.shape[1],1,axis=1)
        x1 = np.insert(x1,x1.shape[1],1,axis=1)
        return x1

    def posterior_ll(self,x,nu,ret_ll_gr_hs=[True,False,False],
            usual_x=False, slc=None):

        #TODO: caching
        if not usual_x:
            if slc is None:
                return ConjugatePair.posterior_ll(self,x,nu,
                    ret_ll_gr_hs=ret_ll_gr_hs,usual_x=usual_x)
            else:       
                # not implemented
                return (None,None,None)

        rt = ret_ll_gr_hs
        ll = None
        gr = None
        hs = None
        wx = np.newaxis

        p = self.prior.dim 
        (mu, psi,k,nu) = self.prior.nat2usual(nu)
        
        nu = nu-p+1
        psi = psi*((k+1)/k/nu)[:,np.newaxis,np.newaxis]


        #see ftp://ftp.ecn.purdue.edu/bethel/kotz_mvt.pdf page 15

        if slc is not None:
            ind = np.zeros(p)==1
            ind[slc] = 1.0
            ind = np.logical_not(ind)

            psi[:,ind,:] = 0
            psi[:,:,ind] = 0
            psi[:,ind,ind] = 1.0
            sgi = np.array(map(np.linalg.inv,psi))
            sgi[:,ind,:] = 0
            sgi[:,:,ind] = 0

            p -= ind.sum()
        else:
            sgi = np.array(map(np.linalg.inv,psi))

        # the only three lines depending on x
        dx = x[:,wx,:] - mu[wx,:,:]

        # TODO: einsum wrong:
        gr = np.einsum('kij,nkj->nki', sgi,dx)

        # TODO: einsum wrong:
        al = 1 + np.einsum('nki,nki->nk', gr,dx)/nu

        if rt[1] or rt[2]:
            bt = -(nu+p)/al/nu

        if rt[0]:   
            ll2 = - .5*(nu+p)*np.log(al)
            ll1 = (  scipy.special.gammaln( .5*(nu+p))
                   - scipy.special.gammaln( .5*(nu)) 
                   - .5*np.array(map(np.linalg.slogdet,psi))[:,1]
                   - .5*p*np.log(nu)
                   )
            ll0 = - .5*p*np.log(np.pi)
            ll = ll2 + ll1 + ll0

        if rt[1]:   
            gr = bt[:,:,wx]*gr

        #TODO: test hessian
        if rt[2]:
            hs = bt[:,:,wx,wx]*sgi+gr[:,:,:,wx]*gr[:,:,wx,:]/(nu+p)[wx,:,wx,wx]
        
        return (ll,gr,hs)
        
        

    # todo: remove:
    def partition(self, nu,slc):
        #TODO: write a test for this

        d = self.prior.dim

        ds = slc.size
        slice_distr = GaussianNIW(ds)

        l1 = nu[:,:d]
        l2 = nu[:,d:-2].reshape(-1,d,d)
        l3 = nu[:,-2:-1]
        l4 = nu[:,-1:]  # should sub from this one

        l1 = l1[:,slc]
        l2 = l2[:,slc,:][:,:,slc]
        l4 = l4 - 2*(d-ds) #TODO: either *2 or *1. not sure which
        
        nus = np.hstack([l1,l2.reshape(l2.shape[0],-1), l3, l4])

        return slice_distr,nus
        
    def plot(self, nu, szs, slc,n = 100,):

        nuE = self.prior.nat2usual(nu[szs>0,:])
        d = self.prior.dim
        mus, Sgs, k, nu = nuE

        # plot the mode of the distribution
        Sgs/=(k + slc.size  + 1)[:,np.newaxis,np.newaxis]
        
        szs /= szs.sum()
         
        for mu, Sg,sz in zip(mus[:,slc],Sgs[:,slc,:][:,:,slc],szs):

            w,V = np.linalg.eig(Sg)
            V =  np.array(np.matrix(V)*np.matrix(np.diag(np.sqrt(w))))

            sn = np.sin(np.linspace(0,2*np.pi,n))
            cs = np.cos(np.linspace(0,2*np.pi,n))
            
            x = V[:,1]*cs[:,np.newaxis] + V[:,0]*sn[:,np.newaxis]
            x += mu
            plt.plot(x[:,1],x[:,0],linewidth=sz*10)

class VDP:
    """ Variational Dirichlet Process clustering algorithm."""
    def __init__(self,distr, w = .1, k=50,
                tol = 1e-5,
                max_iters = 10000):
        """
        Args:
            distr -- likelihood-prior distribution pair governing clusters
            w -- positive prior weight. The prior has as much influence as w data points.
            k -- the maximum number of clusters.
            tol -- convergence tolerance
        """
        
        self.max_iters = max_iters
        self.tol = tol
        self.distr = distr
        self.w = w
        self.k = k
        d = self.distr.sufficient_stats_dim()


        self.prior = self.distr.prior_param
        self.s = np.array([0.0,0])
        
    def batch_learn(self,x1,verbose=False, sort = True):
        n = x1.shape[0] 
        k = self.k
        
        wx = x1[:,-1]
        wt = wx.sum()

        lbd = self.prior + x1.sum(0) / wx.sum() * self.w
        ex_alpha = 1.0
        
        phi = np.random.random(size=n*k).reshape((n,k))

        for t in range(self.max_iters):

            phi /= phi.sum(1)[:,np.newaxis]
            # m step
            tau = (lbd[np.newaxis,:] + np.einsum('ni,nj->ij', phi, x1))
            psz = np.einsum('ni,n->i',phi,wx)

            # stick breaking process
            if sort:
                ind = np.argsort(-psz) 
                tau = tau[ind,:]
                psz = psz[ind]
            
            if t > 0:
                old = al

            al = 1.0 + psz

            if t > 0:
                diff = np.sum(np.abs(al - old))

            bt = ex_alpha + np.concatenate([
                    (np.cumsum(psz[:0:-1])[::-1])
                    ,[0]
                ])

            tmp = scipy.special.psi(al + bt)
            exlv  = (scipy.special.psi(al) - tmp)
            exlvc = (scipy.special.psi(bt) - tmp)

            elt = (exlv + np.concatenate([[0],np.cumsum(exlvc)[:-1]]))

            w = self.s + np.array([-1 + k, -np.sum(exlvc[:-1])])
            ex_alpha = w[0]/w[1]
            
            # end stick breaking process
            # end m step


            # e_step
            grad = self.distr.prior.log_partition(tau,[False,True,False])[1]
            np.einsum('ki,ni->nk',grad,x1,out=phi)

            phi /= wx[:,np.newaxis]
            phi += elt
            phi -= phi.max(1)[:,np.newaxis]
            np.exp(phi,phi)
            
            
            if t>0:
                if verbose:
                    print str(diff)
                if diff < wt*self.tol:
                    break

        self.al = al
        self.bt = bt
        self.tau = tau
        self.lbd = lbd
        self.glp = grad
        self.elt = elt

        return

    def cluster_sizes(self):
        return (self.al -1)
        
        
    def ll(self,x, ret_ll_gr_hs = [True,False,False], **kwargs):

        rt = ret_ll_gr_hs
        llk,grk,hsk = self.distr.posterior_ll(x,self.tau,
                [True,rt[1],rt[2]], **kwargs)

        ll = None
        gr = None
        hs = None

        al = self.al
        bt = self.bt

        tmp = np.log(al + bt)
        exlv  = np.log(al) - tmp
        exlvc = np.log(bt) - tmp
        let = exlv + np.concatenate([[0],np.cumsum(exlvc)[:-1]])

        llk +=let 
        np.exp(llk,llk)

        se = llk.sum(1)
        
        if rt[0]:
            ll = np.log(se)

        if rt[1] or rt[2]:
            p = llk/se[:,np.newaxis]
            gr = np.einsum('nk,nki->ni',p,grk)
        
        if rt[2]:
            hs1  = - gr[:,:,np.newaxis] * gr[:,np.newaxis,:]
            hs2 = np.einsum('nk,nkij->nij',p, hsk)
            # TODO: einsum wrong
            hs3 = np.einsum('nk,nki,nkj->nij',p, grk, grk)

            hs = hs1 + hs2 + hs3
        
        return (ll,gr,hs)


    def resp(self,x, **kwargs):
        llk,grk,hsk = self.distr.posterior_ll(x,self.tau,
                [True,False,False], **kwargs)

        al = self.al
        bt = self.bt

        tmp = np.log(al + bt)
        exlv  = np.log(al) - tmp
        exlvc = np.log(bt) - tmp
        let = exlv + np.concatenate([[0],np.cumsum(exlvc)[:-1]])

        llk +=let
        llk -= llk.max(1)[:,np.newaxis] 
        np.exp(llk,llk)
        se = llk.sum(1)
        p = llk/se[:,np.newaxis]

        return p


    def conditional_ll(self,x,cond):

        ll , gr, hs = self.ll(x,[True,True,True], usual_x=True)
        ll_ , gr_, hs_ = self.ll(x,[True,True,True], 
                slc=cond, usual_x=True)
        
        ll -= ll_
        gr -= gr_
        hs -= hs_

        return (ll,gr,hs)

    def plot_clusters(self,**kwargs):
        sz = self.cluster_sizes()
        self.distr.plot(self.tau, sz, **kwargs)

class OnlineVDP:
    def __init__(self, distr, w=.1, k = 25, tol=1e-3, max_items = 100):
        self.distr = distr
        self.w = w
        self.wm = w
        self.k = k
        self.tol = tol
        self.max_n = max_items

        self.xs = []
        self.vdps = []
        self.dim = self.distr.sufficient_stats_dim()
        
    def put(self,r,s=0):

        if s<len(self.xs):
            ar = np.vstack((self.xs[s],r))
        else:
            ar = r
            self.xs.append(None)
        
        mn = self.max_n*(s+1)

        pcs = ar.shape[0] / mn
        self.xs[s] = ar[pcs*mn:,:]

        if s<len(self.vdps):
            proc = self.vdps[s]
        else:
            if s>0:
                w = self.wm
            else:
                w = self.w
            
            proc = VDP(self.distr, w, self.k*(s+1), self.tol)
            self.vdps.append(proc)

        if pcs==0:
            return        

        for x in np.split(ar[:pcs*self.max_n,:],pcs):
            proc.batch_learn(x,verbose=False)
            xc = proc.tau - proc.lbd[np.newaxis,:]
            xc = xc[xc[:,-1]>1e-5]
            self.put(xc,s+1)

    def get_model(self):

        np.random.seed(1)
        proc = VDP(self.distr, self.wm, self.k*(len(self.xs)), self.tol)
        proc.batch_learn(np.vstack(self.xs[::-1]))
        #print proc.al.sum()
        return proc
        
        

