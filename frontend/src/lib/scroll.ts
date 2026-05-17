export function scrollToId(id: string) {
    const element = document.getElementById(id);

    if (element) {
        element.scrollIntoView({
            behavior: "smooth",
            block: "start",
        });
    }
<<<<<<< HEAD
}
=======
}
>>>>>>> 2783139 (Add frontend scroll utility)
