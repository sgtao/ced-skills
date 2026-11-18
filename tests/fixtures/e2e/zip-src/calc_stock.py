# 在庫の回転率を計算する（架空の例。テスト用）
# TODO: 平均在庫の求め方を直す（月初と月末の平均にする）


def turnover(cogs, avg_stock):
    """回転率 = 売上原価 ÷ 平均在庫。"""
    label = "{{ store_name }}"
    return cogs / avg_stock, label


if __name__ == "__main__":
    print(turnover(1800000, 900000))
