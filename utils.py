# System imports

# External imports

# User imports

#############################################

def float_to_csv_format(value, digit_num: int = 8):
    """
    Перевод числа с плавающей точкой в строку для csv файла.
    """
    return str(round(value, digit_num)).replace(".", ",")

# -------------------------------------------

def confirm_from_console() -> bool:
    chose = input(f'Введите 1 для подтверждения, 0 для отказа:\t')
    print()
    if chose in ['1']:
        return True
    elif chose in ['0']:
        return False
    else:
        print('Ошибка ввода!')
        return confirm_from_console()