import random
import logging
import numpy as np
import torch
from transformers import (
    BertConfig,
    BertTokenizer,
    BertForTokenClassification,
    BertForQuestionAnswering,
    DistilBertConfig,
    DistilBertTokenizer,
    DistilBertForTokenClassification,
    DistilBertForQuestionAnswering,
    #BartConfig, 
    #BartForConditionalGeneration, 
    #BartTokenizer,
    MBartConfig,
    MBartForConditionalGeneration,
    MBartTokenizer
)

# BART
from modeling_transformers.modeling_bart import BartForConditionalGeneration
from modeling_transformers.tokenization_bart import BartTokenizer
from modeling_transformers.configuration_bart import BartConfig

# T5
from modeling_transformers.modeling_t5 import T5ForConditionalGeneration
from modeling_transformers.modeling_mt5 import MT5ForConditionalGeneration
from modeling_transformers.tokenization_t5 import T5Tokenizer
from modeling_transformers.configuration_mt5 import MT5Config

# BERTLM
from modeling_transformers.modeling_bert import BertLMHeadModel
from modeling_transformers.tokenization_bert import BertTokenizer
from modeling_transformers.configuration_bert import BertConfig

#RobertaLM
from modeling_transformers.modeling_roberta import RobertaForCausalLM
from modeling_transformers.tokenization_roberta import RobertaTokenizer
from modeling_transformers.configuration_roberta import RobertaConfig

from FedML.fedml_api.distributed.fedavg.FedAvgAPI import FedML_FedAvg_distributed
from FedML.fedml_api.distributed.fedopt.FedOptAPI import FedML_FedOpt_distributed
from FedML.fedml_api.distributed.fedprox.FedProxAPI import FedML_FedProx_distributed
from model.transformer.bert_model import BertForSequenceClassification
from model.transformer.distilbert_model import DistilBertForSequenceClassification

ADD_TOKEN_LIST = ['‘', '’', '“', '”、“', '两', '语', '校', '项', '”', '”。', '江', '很', '指', '播', '有', '没', '”，', '开', '这', '表', '舍', '你', '是', '”(', '缷', '搾', '喑', '问', '虽', '偘', '——', '鸡', '欢', '’。', '灭', '就', '赶', '光', '殚', '……”', '的', '歌', '……', '因', '世', '样', '对', '绐', '’，', '例', '我', '以', '不', '加', '本', '‘Blocking’', '演', '一', '他', '那', '李', '文', '“Hangul”。', '赤', '和', '东', '恶', '或', '邪', '’，‘', '苦', '“ReinaSopia”', '巴', '去', '看', '陈', '冻', '先', '哥', '爷', '安', '奶', '晚', '二', '好', '爸', '完', '妈', '明']


def get_fl_algorithm_initializer(alg_name):
    if alg_name == "FedAvg":
        fl_algorithm = FedML_FedAvg_distributed
    elif alg_name == "FedOPT":
        fl_algorithm = FedML_FedOpt_distributed
    elif alg_name == "FedProx":
        fl_algorithm = FedML_FedProx_distributed
    else:
        raise Exception("please do sanity check for this algorithm.")

    return fl_algorithm


def create_model(args, formulation="classification"):
    # create model, tokenizer, and model config (HuggingFace style)
    MODEL_CLASSES = {
        "classification": {
            "bert": (BertConfig, BertForSequenceClassification, BertTokenizer),
            "distilbert": (DistilBertConfig, DistilBertForSequenceClassification, DistilBertTokenizer),
            # "roberta": (RobertaConfig, RobertaForSequenceClassification, RobertaTokenizer),
            # "albert": (AlbertConfig, AlbertForSequenceClassification, AlbertTokenizer),
        },
        "seq_tagging": {
            "bert": (BertConfig, BertForTokenClassification, BertTokenizer),
            "distilbert": (DistilBertConfig, DistilBertForTokenClassification, DistilBertTokenizer),
        },
        "span_extraction": {
            "bert": (BertConfig, BertForQuestionAnswering, BertTokenizer),
            "distilbert": (DistilBertConfig, DistilBertForQuestionAnswering, DistilBertTokenizer),
        },
        "seq2seq": {
            "mbart": (MBartConfig, MBartForConditionalGeneration, MBartTokenizer),
            "bart": (BartConfig, BartForConditionalGeneration, BartTokenizer),
            "bart_zh": (BartConfig, BartForConditionalGeneration, BertTokenizer),
            "t5_zh": (T5Config, T5ForConditionalGeneration, BertTokenizer),
            "mt5_zh": (MT5Config, MT5ForConditionalGeneration, BertTokenizer),
            "bert_lm_zh": (BertConfig, BertLMHeadModel, BertTokenizer),
            "roberta_lm_zh": (RobertaConfig, RobertaForCausalLM, BertTokenizer),
        }
    }
    config_class, model_class, tokenizer_class = MODEL_CLASSES[formulation][
        args.model_type]
    
    config = config_class.from_pretrained(args.model_name, **args.config, cache_dir=args.model_type+'_distributed_cache')
    if args.model_type == "bertlm_zh" or args.model_type == "robertalm_zh":
        config.is_decoder = True
    
    model = model_class.from_pretrained(args.model_name, config=config, cache_dir=args.model_type+'_distributed_cache')

    if formulation != "seq2seq":
        tokenizer = tokenizer_class.from_pretrained(
            args.model_name, do_lower_case=args.do_lower_case, cache_dir=args.model_type+'_distributed_cache')
    else:
        tokenizer = [None, None]
        pretrain_tokenizer = tokenizer_class.from_pretrained(args.model_name, cache_dir=args.model_type+'_distributed_cache')
        logging.info(len(pretrain_tokenizer))
        logging.info(len(ADD_TOKEN_LIST))
        num_added_toks = pretrain_tokenizer.add_tokens(ADD_TOKEN_LIST)
        logging.info('Added %d tokens', num_added_toks)
        logging.info(len(pretrain_tokenizer))
        model.resize_token_embeddings(len(pretrain_tokenizer))
        tokenizer[0] = pretrain_tokenizer
        tokenizer[1] = pretrain_tokenizer
        
    
    logging.info('Pretrain Model Name: %s' %(str(args.model_name)))
    logging.info('Config Class: %s' %(str(config_class)))
    logging.info('Model Class: %s' %(str(model_class)))
    logging.info('Tokenizer Class: %s' %(str(tokenizer_class)))
    
    return config, model, tokenizer


def set_seed(seed):
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    np.random.seed(seed)
    random.seed(seed)


def add_federated_args(parser):
    """
    parser : argparse.ArgumentParser
    return a parser added with args required by fit
    """
    # # PipeTransformer related
    parser.add_argument("--run_id", type=int, default=0)

    parser.add_argument("--is_debug_mode", default=0, type=int,
                        help="is_debug_mode")

    # Data related
    # TODO: list all dataset names:
    parser.add_argument('--dataset', type=str, default='agnews', metavar='N',
                        help='dataset used for training')

    parser.add_argument(
        '--data_file_path', type=str,
        default='/home/bill/fednlp_data/data_files/agnews_data.h5',
        help='data h5 file path')

    parser.add_argument(
        '--partition_file_path', type=str,
        default='/home/bill/fednlp_data/partition_files/agnews_partition.h5',
        help='partition h5 file path')

    parser.add_argument('--partition_method', type=str, default='uniform',
                        help='partition method')

    # Model related
    parser.add_argument('--model_type', type=str, default='bert', metavar='N',
                        help='transformer model type')
    parser.add_argument('--model_name', type=str, default='bert-base-uncased', metavar='N',
                        help='transformer model name')
    parser.add_argument('--do_lower_case', type=bool, default=True, metavar='N',
                        help='transformer model name')

    # Learning related
    parser.add_argument('--train_batch_size', type=int, default=8, metavar='N',
                        help='input batch size for training (default: 8)')
    parser.add_argument('--eval_batch_size', type=int, default=8, metavar='N',
                        help='input batch size for evaluation (default: 8)')

    parser.add_argument('--max_seq_length', type=int, default=128, metavar='N',
                        help='maximum sequence length (default: 128)')
    parser.add_argument('--max_length', type=int, default=128, metavar='N',
                        help='maximum decode sequence length (default: 128)')

    parser.add_argument('--n_gpu', type=int, default=1, metavar='EP',
                        help='how many gpus will be used ')

    parser.add_argument('--fp16', default=False, action="store_true",
                        help='if enable fp16 for training')
    parser.add_argument('--manual_seed', type=int, default=42, metavar='N',
                        help='random seed')

    # IO related
    parser.add_argument('--output_dir', type=str, default="/tmp/", metavar='N',
                        help='path to save the trained results and ckpts')

    # Federated Learning related
    parser.add_argument('--fl_algorithm', type=str, default="FedAvg",
                        help='Algorithm list: FedAvg; FedOPT; FedProx ')

    parser.add_argument('--backend', type=str, default="MPI",
                        help='Backend for Server and Client')

    parser.add_argument('--comm_round', type=int, default=10,
                        help='how many round of communications we shoud use')

    parser.add_argument('--is_mobile', type=int, default=1,
                        help='whether the program is running on the FedML-Mobile server side')

    parser.add_argument('--client_num_in_total', type=int, default=-1, metavar='NN',
                        help='number of clients in a distributed cluster')

    parser.add_argument('--client_num_per_round', type=int,
                        default=4, metavar='NN', help='number of workers')
    
    parser.add_argument('--num_beams', type=int,
                        default=4, metavar='NN', help='number of beams')

    parser.add_argument('--epochs', type=int, default=3, metavar='EP',
                        help='how many epochs will be trained locally')

    parser.add_argument('--gradient_accumulation_steps', type=int, default=1, metavar='EP',
                        help='how many steps for accumulate the loss.')

    parser.add_argument('--client_optimizer', type=str, default='adam',
                        help='Optimizer used on the client. This field can be the name of any subclass of the torch Opimizer class.')

    parser.add_argument('--lr', type=float, default=0.1, metavar='LR',
                        help='learning rate on the client (default: 0.001)')

    parser.add_argument('--weight_decay', type=float, default=0, metavar='N',
                        help='L2 penalty')

    parser.add_argument('--server_optimizer', type=str, default='sgd',
                        help='Optimizer used on the server. This field can be the name of any subclass of the torch Opimizer class.')

    parser.add_argument('--server_lr', type=float, default=0.1,
                        help='server learning rate (default: 0.001)')

    parser.add_argument('--server_momentum', type=float, default=0,
                        help='server momentum (default: 0)')

    parser.add_argument('--fedprox_mu', type=float, default=1,
                        help='server momentum (default: 1)')
    parser.add_argument(
        '--evaluate_during_training_steps', type=int, default=100, metavar='EP',
        help='the frequency of the evaluation during training')

    parser.add_argument('--frequency_of_the_test', type=int, default=1,
                        help='the frequency of the algorithms')

    # GPU device management
    parser.add_argument('--gpu_mapping_file', type=str, default="gpu_mapping.yaml",
                        help='the gpu utilization file for servers and clients. If there is no \
                    gpu_util_file, gpu will not be used.')

    parser.add_argument('--gpu_mapping_key', type=str,
                        default="mapping_default",
                        help='the key in gpu utilization file')

    parser.add_argument('--ci', type=int, default=0,
                        help='CI')
    
    # cached related
    parser.add_argument('--reprocess_input_data',  action='store_true',
                        help='whether generate features')
    
    # freeze related
    parser.add_argument('--freeze_layers', type=str, default='', metavar='N',
                        help='freeze which layers')

    return parser
