import re
import math

def clean_area(area_str: str) -> float:
    """
    Chuyển đổi chuỗi diện tích (VD: "108,12 m²", "5.107,5 m²", "80 m2") thành số thực float.
    Hỗ trợ xử lý định dạng số kiểu Việt Nam (dấu '.' chia hàng nghìn, dấu ',' thập phân).
    """
    if not area_str or not isinstance(area_str, str):
        return None
    
    # Loại bỏ "m²", "m2", khoảng trắng
    val = re.sub(r'(?i)m\s*²|m\s*2', '', area_str).strip()
    
    if not val:
        return None
    
    try:
        # Nếu chuỗi có cả dấu chấm và dấu phẩy (VD: 5.107,5)
        if '.' in val and ',' in val:
            val = val.replace('.', '').replace(',', '.')
        # Nếu chỉ có dấu phẩy (thường là số thập phân VD: 36,3)
        elif ',' in val:
            # Kiểm tra xem dấu phẩy là phân cách hàng nghìn hay thập phân
            # Nếu sau dấu phẩy có đúng 3 chữ số thì khả năng cao là phân cách hàng nghìn (VD: 1,000)
            parts = val.split(',')
            if len(parts) == 2 and len(parts[1]) == 3:
                val = val.replace(',', '')
            else:
                val = val.replace(',', '.')
        
        # Giữ lại chỉ số và dấu chấm
        val = re.sub(r'[^0-9.]', '', val)
        return float(val)
    except Exception:
        return None

def clean_price(price_str: str, area_value: float = None) -> float:
    """
    Chuyển đổi các định dạng giá thô thành số thực duy nhất mang đơn vị VNĐ.
    
    Đầu vào hỗ trợ:
    - "24,5 tỷ" -> 24500000000.0
    - "800 triệu" -> 800000000.0
    - "35 triệu/m²" -> 35000000 * area_value (nếu có diện tích)
    - "Giá thỏa thuận" hoặc "Thỏa thuận" -> None
    """
    if not price_str or not isinstance(price_str, str):
        return None
    
    price_str = price_str.strip().lower()
    
    if "thỏa thuận" in price_str or "thoả thuận" in price_str:
        return None

    try:
        # Xử lý trường hợp tính theo m² (VD: "35 triệu/m²", "120 triệu/m2")
        is_per_m2 = False
        if "/m" in price_str:
            is_per_m2 = True
            price_str = price_str.split("/m")[0].strip()

        # Tìm phần số trong chuỗi (VD: "24,5" hoặc "800")
        num_match = re.search(r'[0-9.,]+', price_str)
        if not num_match:
            return None
        
        num_str = num_match.group(0)
        # Chuẩn hóa định dạng số
        if '.' in num_str and ',' in num_str:
            num_str = num_str.replace('.', '').replace(',', '.')
        elif ',' in num_str:
            num_str = num_str.replace(',', '.')
        
        value = float(num_str)

        # Áp dụng nhân hệ số đơn vị
        if "tỷ" in price_str or "ty" in price_str:
            value = value * 1_000_000_000
        elif "triệu" in price_str or "trieu" in price_str or "tr" in price_str:
            value = value * 1_000_000
            
        # Nếu là đơn vị giá/m2, nhân với diện tích để ra tổng giá
        if is_per_m2:
            if area_value and not math.isnan(area_value):
                value = value * area_value
            else:
                return None # Không tính được tổng giá nếu thiếu diện tích

        return round(value, 2)
    except Exception:
        return None

def parse_address(location_str: str) -> dict:
    """
    Tách chuỗi địa chỉ thành 3 trường sạch sẽ: tỉnh/thành phố, quận/huyện, phường/xã.
    Địa chỉ BĐS thường định dạng ngược từ bé đến lớn: "Phường Long Bình, Quận 9, TP.HCM"
    """
    result = {
        "phuong_xa": None,
        "quan_huyen": None,
        "tinh_thanh": None
    }
    
    if not location_str or not isinstance(location_str, str):
        return result
    
    # Tách bằng dấu phẩy
    parts = [p.strip() for p in location_str.split(',') if p.strip()]
    
    if not parts:
        return result
    
    # Do địa chỉ Việt Nam thường viết từ nhỏ đến lớn: Phường -> Quận -> Tỉnh
    # Ta sẽ phân tích ngược từ cuối lên
    if len(parts) >= 1:
        result["tinh_thanh"] = parts[-1]
    if len(parts) >= 2:
        result["quan_huyen"] = parts[-2]
    if len(parts) >= 3:
        result["phuong_xa"] = ", ".join(parts[:-2]) # Phần còn lại ở đầu thường là phường/xã/đường
        
    return result

def extract_market_signals(title: str, description: str) -> dict:
    """
    Phân tích văn bản thô để tìm các tín hiệu/tâm lý đặc biệt của thị trường.
    Rất hữu ích cho phân tích biến động giá gấp ("cắt lỗ", "ngộp ngân hàng",...).
    """
    combined_text = f"{title or ''} {description or ''}".lower()
    
    # Định nghĩa các tập từ khóa
    urgency_keywords = ["cắt lỗ", "cat lo", "bán gấp", "ban gap", "ngộp", "ngop", "vỡ nợ", "vo no", "siết nợ", "siet no", "kẹt tiền", "ket tien", "hạ giá", "ha gia", "giảm giá", "giam gia"]
    has_red_book_keywords = ["sổ đỏ", "so do", "sổ hồng", "so hong", "đã có sổ", "da co so", "sổ riêng", "so rieng"]
    
    has_urgency = any(kw in combined_text for kw in urgency_keywords)
    has_legal_doc = any(kw in combined_text for kw in has_red_book_keywords)
    
    return {
        "is_urgent_sale": has_urgency,    # Tin bán tháo/cắt lỗ/cần tiền gấp
        "has_legal_clearance": has_legal_doc # Đã có sổ đỏ/sổ hồng (tính pháp lý cao)
    }

if __name__ == "__main__":
    print("--- Test Clean Area ---")
    print(clean_area("108,12 m²"))  
    print(clean_area("5.107,5 m2"))  
    print(clean_area("80 m²"))       
    
    print("\n--- Test Clean Price ---")
    print(clean_price("24,5 tỷ"))         
    print(clean_price("800 triệu"))      
    print(clean_price("35 triệu/m²", 100)) 
    print(clean_price("Thỏa thuận"))       
    
    print("\n--- Test Parse Address ---")
    print(parse_address("Phường Long Bình, Quận 9, Hồ Chí Minh"))
    print(parse_address("Đà Nẵng"))

    print("\n--- Test Market Signals ---")
    print(extract_market_signals("Bán gấp cắt lỗ căn hộ 2PN có sổ hồng giá rẻ", "Do ngộp bank cần ra hàng nhanh"))
