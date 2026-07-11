package com.careeros.common.exception;

public class ThrowUtil {

    public static void throwIf(Boolean condition, ExceptionCode exceptionCode) {

        if (condition) {
            throw new BusinessException(exceptionCode);
        }
    }

    public static void throwIf(Boolean condition, Integer code, String message) {

        if (condition) {
            throw new BusinessException(code, message);
        }
    }

    public static void throwIf(Boolean condition, ExceptionCode exceptionCode, String message) {

        if (condition) {
            throw new BusinessException(exceptionCode.getCode(), message);
        }
    }
}
