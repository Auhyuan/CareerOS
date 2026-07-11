package com.careeros.common.exception;

import cn.hutool.core.date.DateUtil;
import com.careeros.common.model.ExceptionResult;
import com.careeros.common.model.Result;
import io.swagger.v3.oas.annotations.Hidden;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@Slf4j
@RestControllerAdvice
@Hidden
public class ExceptionGlobal{


    @Value("${exception.enable}")
    private Boolean enable = true;

    @ExceptionHandler(value = Exception.class)
    public Object handleBusinessException(Exception e, HttpServletRequest request, HttpServletResponse response) {

        boolean businessException = e instanceof BusinessException;
        int status = businessException ? HttpStatus.BAD_REQUEST.value() : HttpStatus.INTERNAL_SERVER_ERROR.value();

        if (enable) {
            String error = businessException ? HttpStatus.BAD_REQUEST.getReasonPhrase() : HttpStatus.INTERNAL_SERVER_ERROR.getReasonPhrase();

            response.setStatus(status);

            return ExceptionResult.builder()
                    .status(status)
                    .error(error)
                    .message(businessException ? e.getMessage() : ExceptionCode.SYSTEM_ERROR.getMessage())
                    .code(businessException ? ((BusinessException) e).getCode() : ExceptionCode.SYSTEM_ERROR.getCode())
                    .path(request.getRequestURI())
                    .exception(e.getClass().getName())
                    .errorMessage(e.getMessage())
                    .data(null)
                    .timestamp(DateUtil.now())
                    .build();
        }


        if (e instanceof BusinessException) {
            log.error("BusinessException【{}】: {}", ((BusinessException) e).getCode(), e.getMessage());
            return Result.fail(((BusinessException) e).getCode(), e.getMessage());
        }


        return Result.fail(ExceptionCode.SYSTEM_ERROR.getCode(), ExceptionCode.SYSTEM_ERROR.getMessage());
    }

}
