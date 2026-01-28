from pycrate_asn1dir import RRCNR
from pycrate_asn1rt.utils import bitstr_to_bytes  # 用于位字符串
import json

def decode_asn1_hex(hex_stream, field_name="DL_CCCH_Message"):
    """
    解码ASN.1 UPER格式的hex stream
    
    Args:
        hex_stream (str): 16进制字符串，不需要'0x'前缀
        field_name (str): ASN.1结构名称，默认为'DL_CCCH_Message'
        
    Returns:
        dict: 解码后的Python对象
    """
    # 转换hex为字节 - 使用Python标准库
    asn1_bytes = bytes.fromhex(hex_stream)
    
    # 获取ASN.1结构定义
    sch = getattr(RRCNR.NR_RRC_Definitions, field_name)
    
    # 解码为ASN.1对象
    sch.from_uper(asn1_bytes)
    
    # 获取解码后的Python对象
    asn1_obj = sch.get_val()

    print(asn1_obj)
    
    return asn1_obj

# 如果输入是位字符串而不是十六进制
def decode_asn1_bitstr(bitstream, field_name="DL_CCCH_Message"):
    """
    解码ASN.1 UPER格式的位字符串
    
    Args:
        bitstream (str): 位字符串，如'010101...'
        field_name (str): ASN.1结构名称
        
    Returns:
        dict: 解码后的Python对象
    """
    # 转换位字符串为字节
    asn1_bytes = bitstr_to_bytes(bitstream)
    
    # 获取ASN.1结构定义
    sch = getattr(RRCNR.NR_RRC_Definitions, field_name)
    
    # 解码为ASN.1对象
    sch.from_uper(asn1_bytes)
    
    # 获取解码后的Python对象
    asn1_obj = sch.get_val()
    
    return asn1_obj

def save_to_json(asn1_obj, output_file="01_decoded.json"):
    """将解码后的对象保存为JSON文件"""
    with open(output_file, 'w') as f:
        json.dump(asn1_obj, f, indent=2)
    print(f"已保存到 {output_file}")

# 使用示例
if __name__ == "__main__":
    # 根据输入类型选择适当的函数
    
    # 对于十六进制字符串
    hex_stream = "28400414a2e00580088bd76380830f8003e0102341e040002096cc0ca8040ffff8000000080001b8a210000400b28000241000022049ccb3865994105fffe000000020001b8c410000040414850361cb2a0105fffe0000000200006e59040001002ca0000904000098126d31adb194107fe00000000020001b8e610000040414850361cb2a0107fe000000000200006e61840001002ca00009040000a8126db0c5a994109e000000000060001b9081000004041486a431632a0109e0000000000600006e6a040001002ca00009040000b81264ac6aa49a8000200404000800d010013b649180ee03ab3c4d5e0000014d080100012c061060160e0c10e0018940e0000108f7a0080008000032000a00132670cb339c5a98b6f169a3d327098144235524d40001002020004006808009db248c07701d59e26af000000a684008000960308300b0706087000c4a07040187bd0041004000019023020280034635b6339c5a98b6f169a3d327098144235524d40001002020004006808009db248c07701d59e26af000000a684008000960308300b0706087000c4a07080287bd004200400000c023020280036618b5339c5a98b6f169a3d327098144235524d40001002020004006808009db248c07701d59e26af000000a684008000960308300b0706087000c4a070c0387bd004300400000502302028001ca82803115554009c00c13aa002a210028000380982754001c420050500702304ea800008400a1400100000000200080400109c1740054a0070dd00072829c5740000a140800001010404000000102a40300a000c17000c2c40501200541900542e40701a009c1b009c29681022c80708238c7e068800b024040415305a0810c201c408e31f81a20030110102054c1683063480718238c7e068800d064040c153000"
    decoded_obj = decode_asn1_hex(hex_stream)
    
    # 或者对于位字符串
    # bitstream = "01000000000101100000..."
    # decoded_obj = decode_asn1_bitstr(bitstream)
    
    # 打印解码结果
    print("解码结果:")
    print(decoded_obj)
    
    # 保存为JSON
    save_to_json(decoded_obj)