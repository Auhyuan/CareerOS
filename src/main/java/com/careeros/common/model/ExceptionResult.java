package com.careeros.common.model;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serial;
import java.io.Serializable;

@Data
@AllArgsConstructor
@NoArgsConstructor
@Builder
public class ExceptionResult implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    @Schema(description = "HTTP响应状态码")
    private Integer status;

    @Schema(description = "HTTP错误描述")
    private String error;

    @Schema(description = "对外展示的异常提示信息")
    private String message;

    @Schema(description = "业务错误码")
    private Integer code;

    @Schema(description = "请求路径")
    private String path;

    @Schema(description = "异常类全限定名")
    private String exception;

    @Schema(description = "原始异常信息")
    private String errorMessage;

    @Schema(description = "响应数据，异常时通常为 null")
    private Object data;

    @Schema(description = "异常发生时间")
    private String timestamp;

}
