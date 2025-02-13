import torch
"""
Library of data augmentations for genomic sequence data. 

To contribute a custom augmentation, use the following syntax:
```
    class CustomAugmentation(AugmentBase):
        def __init__(self, param1, param2, ..., paramN):
            self.param1 = param1
            self.param1 = param1
                .
                .
                .
            self.paramN = paramN
        def __call__(self, x):
            # perform augmentation

            return x_aug
```

"""

class AugmentBase():
    """ 
    Base clas for EvoAug augmentations for genomic sequences.
    """
    def __call__(self, x):
        raise NotImplementedError()


class RandomDeletion(AugmentBase):
    """Randomly deletes a contiguous stretch of nucleotides from sequences in a training 
    batch according to a random number between a user-defined delete_min and delete_max.
    A different deletion is applied to each sequence.

    :param delete_min: Minimum size for random deletion, defaults to 0
    :type int
    :param delete_max: Maximum size for random deletion, defaults to 30
    :type int
    """
    def __init__(self, delete_min=0, delete_max=30):
        """Creates random deletion object usable by EvoAug.
        """
        self.delete_min = delete_min
        self.delete_max = delete_max

    def __call__(self, x):
        """Randomly deletes segments in a set of one-hot DNA sequences, x.

        Returns a batch of sequences with the augmentation applied.

        :param x: Batch of sequences (shape: (N, A, L))
        :return: sequences with randomly deleted segments (padded to correct shape with random DNA)

        """
        N, A, L = x.shape   

        # sample random DNA
        a = torch.eye(A)
        p = torch.tensor([1/A for _ in range(A)])
        padding = torch.stack([a[p.multinomial(self.delete_max, replacement=True)].transpose(0,1) for _ in range(N)]).to(x.device)
        
        # sample deletion length for each sequence
        delete_lens = torch.randint(self.delete_min, self.delete_max + 1, (N,))

        # sample locations to delete for each sequence
        delete_inds = torch.randint(L - self.delete_max + 1, (N,)) # deletion must be in boundaries of seq.
        
        # loop over each sequence
        x_aug = []
        for seq, pad, delete_len, delete_ind in zip(x, padding, delete_lens, delete_inds):

            # get index of half delete_len (to pad random DNA at beginning of sequence)
            pad_begin_index = torch.div(delete_len, 2, rounding_mode='floor').item()
            
            # index for other half (to pad random DNA at end of sequence)
            pad_end_index = delete_len - pad_begin_index
            
            # removes deletion and pads beginning and end of sequence with random DNA to ensure same length
            x_aug.append( torch.cat([pad[:,:pad_begin_index],                # random dna padding
                                     seq[:,:delete_ind],                     # sequence up to deletion start index
                                     seq[:,delete_ind+delete_len:],          # sequence after deletion end index
                                     pad[:,self.delete_max-pad_end_index:]], # random dna padding
                                    -1)) # concatenation axis
        return torch.stack(x_aug)





class RandomInsertion(AugmentBase):
    """Randomly inserts a contiguous stretch of nucleotides from sequences in a training 
    batch according to a random number between a user-defined insert_min and insert_max.
    A different insertions is applied to each sequence. Each sequence is padded with random
    DNA to ensure same shapes.

    :param insert_min: Minimum size for random insertion, defaults to 0
    :type int
    :param insert_max: Maximum size for random insertion, defaults to 30
    :type int
    """
    def __init__(self, insert_min=0, insert_max=30):
        """Creates random insersion object usable by EvoAug.
        """
        self.insert_min = insert_min
        self.insert_max = insert_max

    def __call__(self, x):
        """Randomly inserts segments of random DNA to a set of one-hot DNA sequences, x.

        Returns a batch of sequences with the augmentation applied.

        :param x: Batch of sequences (shape: (N, A, L))
        :return: sequences with randomly inserts segments of random DNA -- all sequences padded with random DNA to ensure same shape

        """
        N, A, L = x.shape

        # sample random DNA
        a = torch.eye(A)
        p = torch.tensor([1/A for _ in range(A)])
        insertions = torch.stack([a[p.multinomial(self.insert_max, replacement=True)].transpose(0,1) for _ in range(N)]).to(x.device)

        # sample insertion length for each sequence
        insert_lens = torch.randint(self.insert_min, self.insert_max + 1, (N,))

        # sample locations to insertion for each sequence
        insert_inds = torch.randint(L, (N,))

        # loop over each sequence
        x_aug = []
        for seq, insertion, insert_len, insert_ind in zip(x, insertions, insert_lens, insert_inds):

            # get index of half insert_len (to pad random DNA at beginning of sequence)
            insert_beginning_len = torch.div((self.insert_max - insert_len), 2, rounding_mode='floor').item()

            # index for other half (to pad random DNA at end of sequence)
            insert_end_len = self.insert_max - insert_len - insert_beginning_len
    
            # removes deletion and pads beginning and end of sequence with random DNA to ensure same length
            x_aug.append( torch.cat([insertion[:,:insert_beginning_len],                                # random dna padding
                                     seq[:,:insert_ind],                                                # sequence up to insertion start index
                                     insertion[:,insert_beginning_len:insert_beginning_len+insert_len], # random insertion
                                     seq[:,insert_ind:],                                                # sequence after insertion end index
                                     insertion[:,insert_beginning_len+insert_len:self.insert_max]],     # random dna padding
                                    -1)) # concatenation axis
        return torch.stack(x_aug)




class RandomTranslocation(AugmentBase):
    """Randomly cuts sequence in two pieces and shifts the order for each in a training 
    batch. This is implemented with a roll transformation with a user-defined shift_min 
    and shift_max. A different roll (positive or negative) is applied to each sequence. 
    Each sequence is padded with random DNA to ensure same shapes.

    :param shift_min: Minimum size for random shift, defaults to 0
    :type int
    :param shift_max: Maximum size for random shift, defaults to 30
    :type int
    """
    def __init__(self, shift_min=0, shift_max=30):
        """Creates random shift object usable by EvoAug.
        """
        self.shift_min = shift_min
        self.shift_max = shift_max

    def __call__(self, x):
        N = x.shape[0]
        """Randomly shifts sequences in a batch, x.

        Returns a batch of sequences with the augmentation applied.

        :param x: Batch of sequences (shape: (N, A, L))
        :return: sequences with randomly shifts.

        """

        # determine size of shifts for each sequence
        shifts = torch.randint(self.shift_min, self.shift_max + 1, (N,))

        # make some of the shifts negative
        ind_neg = torch.rand(N) < 0.5
        shifts[ind_neg] = -1 * shifts[ind_neg]

        # apply random shift to each sequence
        x_rolled = []
        for i, shift in enumerate(shifts):
            x_rolled.append( torch.roll(x[i], shift.item(), -1) )
        x_rolled = torch.stack(x_rolled).to(x.device)
        return x_rolled



class RandomInversion(AugmentBase):
    """Randomly inverts a contiguous stretch of nucleotides from sequences in a training 
    batch according to a user-defined invert_min and invert_max. A different insertions 
    is applied to each sequence. Each sequence is padded with random DNA to ensure same 
    shapes.

    :param invert_min: Minimum size for random insertion, defaults to 0
    :type int
    :param invert_max: Maximum size for random insertion, defaults to 30
    :type int
    """
    def __init__(self, invert_min=0, invert_max=30):
        """Creates random inversion object usable by EvoAug.
        """
        self.invert_min = invert_min
        self.invert_max = invert_max

    def __call__(self, x):
        """Randomly inverts segments of random DNA to a set of one-hot DNA sequences, x.

        Returns a batch of sequences with the augmentation applied.

        :param x: Batch of sequences (shape: (N, A, L))
        :return: sequences with randomly inverted segments of random DNA.

        """
        N, A, L = x.shape

        # set random inversion size for each seequence
        inversion_lens = torch.randint(self.invert_min, self.invert_max + 1, (N,))

        # randomly select start location for each inversion
        inversion_inds = torch.randint(L - self.invert_max + 1, (N,)) # inversion must be in boundaries of seq.

        # apply random inversion to each sequence
        x_aug = []
        for seq, inversion_len, inversion_ind in zip(x, inversion_lens, inversion_inds):
            x_aug.append( torch.cat([seq[:,:inversion_ind],    # sequence up to inversion start index
                                     torch.flip(seq[:,inversion_ind:inversion_ind+inversion_len], dims=[0,1]), # reverse-complement transformation
                                     seq[:,inversion_ind+inversion_len:]], # sequence after inversion 
                                    -1)) # concatenation axis
        return torch.stack(x_aug)

        

class RandomMutation(AugmentBase):
    """Randomly mutates sequences in a training batch according to a user-defined mutate_frac.
    A different set of mutations is applied to each sequence. 

    :param mutate_frac: probability of mutation for each nucleotide, defaults to 0.1
    :type float
    """
    def __init__(self, mutate_frac=0.1):
        """Creates random mutation object usable by EvoAug.
        """
        self.mutate_frac = mutate_frac

    def __call__(self, x):
        """Randomly introduces mutations to a set of one-hot DNA sequences, x.

        Returns a batch of sequences with the augmentation applied.

        :param x: Batch of sequences (shape: (N, A, L))
        :return: sequences with randomly mutated DNA.

        """
        N, A, L = x.shape

        # determine the number of mutations per sequence 
        num_mutations = round(self.mutate_frac / 0.75 * L) # num. mutations per sequence (accounting for silent mutations)

        # randomly determine the indices to apply mutations 
        mutation_inds = torch.argsort(torch.rand(N,L))[:, :num_mutations] # see <https://discuss.pytorch.org/t/torch-equivalent-of-numpy-random-choice/16146>0

        # create random DNA (to serve as random mutations)
        a = torch.eye(A)
        p = torch.tensor([1/A for _ in range(A)])
        mutations = torch.stack([a[p.multinomial(num_mutations, replacement=True)].transpose(0,1) for _ in range(N)]).to(x.device)
        
        # make a copy of the batch of sequences
        x_aug = torch.clone(x)

        # loop over sequences and apply mutations
        for i in range(N):
            x_aug[i,:,mutation_inds[i]] = mutations[i]
        return x_aug



class RandomRC(AugmentBase):
    """Randomly applies a reverse-complement transformation to each sequence in a training 
    batch according to a user-defined probability, rc_prob. This is applied to each sequence
    independently. 

    :param rc_prob: probility to apply a reverse-complement transformation, defaults to 0.5
    :type float
    """
    def __init__(self, rc_prob=0.5):
        """Creates random reverse-complement object usable by EvoAug.
        """
        self.rc_prob = rc_prob

    def __call__(self, x):
        """Randomly transforms sequences in a batch with a reverse-complement transformation.

        Returns a batch of sequences with the augmentation applied.

        :param x: Batch of sequences (shape: (N, A, L))
        :return: sequences with random reverse-complements applied.

        """

        # make a copy of the sequence
        x_aug = torch.clone(x)  

        # randomly select sequences to apply rc transformation
        ind_rc = torch.rand(x_aug.shape[0]) < self.rc_prob

        # apply reverse-complement transformation
        x_aug[ind_rc] = torch.flip(x_aug[ind_rc], dims=[1,2])   
        return x_aug



class RandomNoise(AugmentBase):
    """Randomly add Gaussian noise to a batch of sequences with according to a user-defined 
    noise_mean and noise_std. A different set of noise is applied to each sequence. 

    :param noise_mean: Bias of the noise -- mean of Gaussian, defaults to 0.0
    :type float
    :param noise_std: Standard deviation of Gaussian, defaults to 0.2
    :type float
    """
    def __init__(self, noise_mean=0.0, noise_std=0.2):
        """Creates random noise object usable by EvoAug.
        """
        self.noise_mean = noise_mean
        self.noise_std = noise_std

    def __call__(self, x):
        """Randomly adds Gaussian noise to a set of one-hot DNA sequences, x.

        Returns a batch of sequences with the augmentation applied.

        :param x: Batch of sequences (shape: (N, A, L))
        :return: sequences with random noise

        """
        return x + torch.normal(self.noise_mean, self.noise_std, x.shape).to(x.device)












