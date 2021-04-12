from torchvision import models
import torch.nn as nn
import torch
import timm
from transformers import (
    WEIGHTS_NAME,
    AdamW,
    AutoConfig,
    AutoModel,
    AutoTokenizer,
    MMBTConfig,
    MMBTForClassification,
    get_linear_schedule_with_warmup,
    BertModel
)
import torchvision

POOLING_BREAKDOWN = {1: (1, 1), 2: (2, 1), 3: (3, 1), 4: (2, 2), 5: (5, 1), 6: (3, 2), 7: (7, 1), 8: (4, 2), 9: (3, 3)}


#  TODO: 1. image feature extractor
#  2. transformer encoder

class CNN_Image_Encoder(nn.Module):
    def __init__(self):
        super(CNN_Image_Encoder, self).__init__()
        self.cnn = timm.create_model('resnet50', pretrained=True, num_classes=0)
        for para in self.cnn.parameter():
            assert para.require_grad is True

    def forward(self, x):
        return self.cnn(x)  # torch.Size([bz, 2048])


class Transformer_Image_Encoder(nn.Module):
    def __init__(self):
        super(Transformer_Image_Encoder, self).__init__()
        self.encoder = timm.create_model('vit_base_patch16_224', pretrained=False, num_classes=3)
        for para in self.encoder.parameter():
            assert para.require_grad is True

    def forward(self, x):
        return self.encoder.forward_features(x)  # torch.Size([bz, 768])


class ViT_Image_Encoder(nn.Module):
    def __init__(self):
        super(ViT_Image_Encoder, self).__init__()
        self.encoder = timm.create_model('vit_base_patch16_224', pretrained=True, num_classes=3)
        for para in self.encoder.parameter():
            assert para.require_grad is True

    def forward(self, x):
        return self.encoder.forward_features(x)  # torch.Size([bz, 768])


class MMBT_ImageEncoder(nn.Module):
    def __init__(self):
        super().__init__()
        model = torchvision.models.resnet152(pretrained=True)
        modules = list(model.children())[:-2]
        self.model = nn.Sequential(*modules)
        self.pool = nn.AdaptiveAvgPool2d(POOLING_BREAKDOWN[1])  ## output_size = (1,1)

    def forward(self, x):
        # Bx3x224x224 -> Bx2048x7x7 -> Bx2048xN -> BxNx2048
        out = self.pool(self.model(x))
        out = torch.flatten(out, start_dim=2)
        out = out.transpose(1, 2).contiguous()
        return out  # BxNx2048, N = 1


class MMBT(nn.Module):
    def __init__(self, num_labels):
        super(MMBT, self).__init__()
        self.image_encoder = MMBT_ImageEncoder()
        self.transformer_config = AutoConfig.from_pretrained("bert-base-uncased")
        self.transformer = AutoModel.from_pretrained(
            "bert-base-uncased", config=self.transformer_config
        )
        self.config = MMBTConfig(self.transformer_config, num_labels=num_labels)
        self.model = MMBTForClassification(self.config, self.transformer, self.image_encoder)

    def forward(self, input_image, input_text, labels):
        # B x (text + image) -> loss : B x 1 , logits: B x labels
        return self.model(input_image, input_text, labels=labels)


class BERT_Text_Encoder(nn.Module):
    def __init__(self, bert_version: str = "bert-base-uncased"):
        super(BERT_Text_Encoder, self).__init__()
        self.bert = BertModel.from_pretrained(bert_version)
        for para in self.encoder.parameter():
            assert para.require_grad is True

    def forward(self, **inputs):
        bert_outputs, _ = self.bert(
            inputs['input_token_ids'],
            token_type_ids=inputs['input_token_types'].lt(0),
            attention_mask=inputs['input_token_ids'].ne(0))  ## bz x len_seq x hidden_size

        cls_outputs = bert_outputs[:, 0, :]  ## bz x hidden_size
        return cls_outputs


def choose_image_encoder(args):
    if args.image_encoder == "cnn":
        return CNN_Image_Encoder()
    elif args.image_encoder == "transformer":
        return Transformer_Image_Encoder()
    elif args.image_encoder == "vit":
        return ViT_Image_Encoder()
    else:
        raise ValueError("unknown image encoder")


def choose_multi_encoder(args):
    if args.mixed_encoder == "mmbt":
        return MMBT(args.num_label)
    else:
        raise ValueError("unknown multimodal encoder")


def choose_text_encoder(args):
    if args.text_encoder == "bert":
        return BERT_Text_Encoder()
    else:
        raise ValueError("unknown text encoder")
