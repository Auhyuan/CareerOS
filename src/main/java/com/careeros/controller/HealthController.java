package com.careeros.controller;

import com.careeros.common.exception.ThrowUtil;
import com.careeros.common.model.Result;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.servlet.http.HttpServletRequest;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.boot.context.event.ApplicationStartedEvent;
import org.springframework.context.event.EventListener;
import org.springframework.web.bind.annotation.*;

import java.io.Serial;
import java.io.Serializable;

@Slf4j
@RestController
@RequestMapping("/health")
@Tag(name = "健康检查")
public class HealthController {

    @GetMapping()
    @Operation(summary = "健康检测")
    public String health() {

        log.info("health");
        return "ok";
    }

    @GetMapping("/h")
    @Operation(summary = "test")
    public Long id() {
        return 100031314564L;
    }

    @PostMapping("/exception")
    @Operation(summary = "异常测试")
    public void exception() {

        ThrowUtil.throwIf(true,40000,"测试异常");
        int a = 1 / 0;
    }


    @EventListener
    public void on(ApplicationStartedEvent event) {
        log.info("服务已启动");
        log.info("请通过 http://localhost:8080/doc.html 进行接口测试");
    }
}
