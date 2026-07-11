package com.careeros.common.exception;

import lombok.Getter;

@Getter
public enum ExceptionCode {

    UNAUTHORIZED(40100, "未登录或登录已过期"),
    FORBIDDEN(40300, "无权限访问"),
    NOT_FOUND(40400, "资源不存在"),
    PARAM_ERROR(40000, "请求参数错误"),
    BUSINESS_ERROR(40001, "业务处理失败"),
    SYSTEM_ERROR(50000, "系统异常");

    private final Integer code;
    private final String message;

    ExceptionCode(Integer code, String message) {
        this.code = code;
        this.message = message;
    }

    public static ExceptionCode getByCode(Integer code) {
        if (code == null) {
            return null;
        }
        for (ExceptionCode exceptionCode : values()) {
            if (exceptionCode.getCode().equals(code)) {
                return exceptionCode;
            }
        }
        return null;
    }
}
