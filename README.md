# original Code

SAViT from [here](https://github.com/libeineu/fairseq_mmt)
NRCM from [here](https://github.com/nlp-mmt/Noise-robust-Text2image-Mask)
CMA from [here](https://github.com/JunjieYe-MMT/HierProMul-Trans)
following all of them steps to downloads the code and run the original results

# SAViT

change the file call "selective_attention.py" on /fairseq_mmt/fairseq/modules/
and run again 

# NRCM

change the file call "transformer_layer.py" on /Noise-robust-Text2image-Mask/fairseq/modules/
and run again 

# CMA

change the file call "__init__.py" on /HierProMul-Trans/fairseq/modules
                     "multihead_attention.py" on /HierProMul-Trans/fairseq/modules
                     "transformer_layer.py" on /HierProMul-Trans/fairseq/modules
and run again 
