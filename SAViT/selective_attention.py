# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import torch
from fairseq.incremental_decoding_utils import with_incremental_state
from torch import nn
import ot

def Linear(in_features, out_features, bias=True):
    m = nn.Linear(in_features, out_features, bias)
    nn.init.xavier_uniform_(m.weight)
    if bias:
        nn.init.constant_(m.bias, 0.0)
    return m

@with_incremental_state
class SelectiveAttention(nn.Module):
    def __init__(self, qdim, kdim, vdim, attn_dim, intermediate_dim, output_dim, num_heads=1, qkv_bias=True, attn_drop=0.):
        super().__init__()
        self.num_heads = num_heads
        self.qdim = qdim
        self.kdim = kdim
        self.vdim = vdim
        self.output_dim = output_dim
        self.intermediate_dim = intermediate_dim

        self.qkhead_dim = attn_dim // num_heads
        self.vhead_dim = intermediate_dim // num_heads               
        self.scale = self.qkhead_dim ** -0.5

        self.q_proj = Linear(qdim, attn_dim, bias=qkv_bias)
        self.k_proj = Linear(kdim, attn_dim, bias=qkv_bias)
        self.v_proj = Linear(vdim, intermediate_dim, bias=qkv_bias)   
        
        self.attn_drop = nn.Dropout(attn_drop)
        self.proj = Linear(intermediate_dim, output_dim)

    def forward(self, query, key, value, key_padding_mask=None):
        Tq, Bq, Cq = query.shape
        Tk, Bk, Ck = key.shape
        Tv, Bv, Cv = value.shape
        assert Bq == Bk == Bv
        assert Tk == Tv
        assert Cq == self.qdim
        assert Ck == self.kdim
        assert Cv == self.vdim
        bsz = Bq
        
        q = self.q_proj(query)
        k = self.k_proj(key)
        v = self.v_proj(value)
       
        q *= self.scale
        
        q = q.contiguous().view(Tq, bsz * self.num_heads, self.qkhead_dim).transpose(0, 1)
        k = k.contiguous().view(-1, bsz * self.num_heads, self.qkhead_dim).transpose(0, 1)
        v = v.contiguous().view(-1, bsz * self.num_heads, self.vhead_dim).transpose(0, 1)
        # B*H, T, C//H

        attn = (q @ k.transpose(-2, -1)) 
        if key_padding_mask is not None:
            attn = attn.view(bsz, self.num_heads, Tq, Tk)
            attn = attn.masked_fill(key_padding_mask.unsqueeze(1).unsqueeze(2).to(torch.bool), float("-inf"))
            attn = attn.view(bsz * self.num_heads, Tq, Tk)

        attn = attn.softmax(dim=-1)

        #OT start  
        
        sh1 = attn.shape[0]
        sh2 = attn.shape[1]
        sh3 = attn.shape[2]
        attn = attn.cuda().detach().reshape(-1,577)
        S = attn
        Sbatchsize = len(attn)
        T = q.cpu().detach().reshape(-1,128)
        lambd = 0.05
        S_hat = torch.zeros_like(attn)

        for i in range(sh2):
            S_fg = attn[i]
            cost_mat = torch.ones_like(attn)
            cost_mat = cost_mat - S_fg
            num_fg_pix = attn.shape[1]
            num_text = T.shape[0]
            cost_mat =cost_mat.to(torch.float32)

            a = 1./num_text
            a = (a * torch.ones(num_text)).to('cuda')
            b = 1./num_fg_pix
            b = (b * torch.ones(num_fg_pix)).to('cuda')

            attn = ot.sinkhorn(a, b, cost_mat, lambd, numItermax = 200)

        attn = attn.view(sh1,sh2,sh3)        
        #OT end

        attn_after_drop = self.attn_drop(attn)
        attn_after_drop = attn_after_drop.to('cuda')
        v = v.to(torch.float32)
        x = (attn_after_drop @ v)
        assert list(x.size()) == [bsz * self.num_heads, Tq, self.vhead_dim]
        x = x.transpose(0, 1).contiguous().view(Tq, bsz, self.intermediate_dim)

        # translate float32 train float16
        x = x.to(torch.float16)
        
        x = self.proj(x)

        return x, attn
