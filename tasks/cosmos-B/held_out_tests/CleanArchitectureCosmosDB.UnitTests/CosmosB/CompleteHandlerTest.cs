using CleanArchitectureCosmosDB.Core.Entities;
using CleanArchitectureCosmosDB.Core.Exceptions;
using CleanArchitectureCosmosDB.UnitTests.CosmosB.TestDoubles;
using CleanArchitectureCosmosDB.WebAPI.Models.ToDoItem;
using System.Threading;
using System.Threading.Tasks;
using Xunit;

namespace CleanArchitectureCosmosDB.UnitTests.CosmosB
{
    public class CompleteHandlerTest
    {
        [Fact]
        public async Task Complete_MarksExistingItemCompleted_AndPersists()
        {
            InMemoryToDoItemRepository repo = new InMemoryToDoItemRepository();
            ToDoItem item = new ToDoItem() { Id = "work:1", Category = "work", Title = "Finish me" };
            await repo.AddItemAsync(item);

            Complete.CommandHandler handler = HandlerFactory.Create<Complete.CommandHandler>(repo);
            await handler.Handle(new Complete.CompleteToDoItemCommand() { Id = "work:1" }, CancellationToken.None);

            ToDoItem stored = await repo.GetItemAsync("work:1");
            Assert.True(stored.IsCompleted);
        }

        [Fact]
        public async Task Complete_UnknownId_ThrowsEntityNotFound()
        {
            InMemoryToDoItemRepository repo = new InMemoryToDoItemRepository();

            Complete.CommandHandler handler = HandlerFactory.Create<Complete.CommandHandler>(repo);

            await Assert.ThrowsAsync<EntityNotFoundException>(() =>
                handler.Handle(new Complete.CompleteToDoItemCommand() { Id = "missing:1" }, CancellationToken.None));
        }
    }
}
